import logging
import math
import os
import shutil
import time
from typing import Dict, Any, List
from app.services.catia_bridge import catia_bridge

logger = logging.getLogger(__name__)

# CATIA SPA GetBoundaryBox returns meters; we report mm
MM_PER_M = 1000.0

# Names of bodies to ignore (typical construction geometry in die design)
IGNORE_BODY_KEYWORDS = ["STOCK", "BOUNDING", "ENVELOPE", "BOX", "CONSTRUCTION", "AXIS", "WIRE", "SURFACE"]

class GeometryService:
    def _get_com(self, obj: Any) -> Any:
        try:
            if hasattr(obj, "com_object"): return obj.com_object
            return obj
        except: return obj

    def get_bounding_box(self, part_or_product: Any, fast_mode: bool = False) -> Dict[str, Any]:
        """Calculates the bounding box of a Part or Product using multiple Tiers.
        Three-Tier Measurement Strategy:
        1. Direct SPA (Fastest, CGR-capable)
        2. Copy-Paste Flattening (Standard Nuclear)
        3. NewFrom Context-Breaker (Surgical Fallback for STEP/Context locks)
        """
        logger.info(f"GeometryService: get_bounding_box for {getattr(part_or_product, 'Name', 'Unknown')}")
        
        caa = self._get_com(catia_bridge.get_application())
        if not caa: 
            logger.info("GeometryService: CATIA not found")
            return self._get_fallback_bbox()
        
        raw_pop = self._get_com(part_or_product)
        if not raw_pop:
            logger.info("GeometryService: Received null part_or_product")
            return self._get_fallback_bbox()

        # 1. Assembly Handling
        try:
            if hasattr(raw_pop, "Products") and raw_pop.Products.Count > 0:
                logger.info(f"GeometryService: Handling as Product/Assembly: {raw_pop.Name}")
                return self.get_product_bounding_box(raw_pop)
        except: pass

        # 2. TIER 1: Direct SPA (Try first as it's fastest)
        try:
            active_doc = self._resolve_document(raw_pop) or caa.ActiveDocument
            active_doc.Activate()
            
            sel = active_doc.Selection
            spa = active_doc.GetWorkbench("SPAWorkbench")
            
            # Use Selection as a middle-man to get a stable measurable object
            targets = [raw_pop]
            try:
                if hasattr(raw_pop, "ReferenceProduct"):
                    targets.append(raw_pop.ReferenceProduct)
            except: pass
            
            for target in targets:
                try:
                    # Force Design Mode for measurement
                    try:
                        if hasattr(target, "ApplyDesignMode"): target.ApplyDesignMode()
                    except: pass
                    
                    sel.Clear()
                    sel.Add(target)
                    # Force show for accuracy
                    try: sel.VisProperties.SetShow(0)
                    except: pass
                    
                    if sel.Count > 0:
                        try:
                            # Preferred: Item.Reference for GetMeasurable
                            val = sel.Item(1).Reference
                            measurable = spa.GetMeasurable(val)
                        except:
                            # Fallback: Item.Value
                            val = sel.Item(1).Value
                            measurable = spa.GetMeasurable(val)
                            
                        bb = [0.0] * 6
                        bb = measurable.GetBoundaryBox(bb)
                        if bb and len(bb) >= 6:
                            dx, dy, dz = abs(bb[1]-bb[0]), abs(bb[3]-bb[2]), abs(bb[5]-bb[4])
                            dx, dy, dz = dx * MM_PER_M, dy * MM_PER_M, dz * MM_PER_M
                            if dx > 0.1:
                                res = self._round_bbox({
                                    "x": dx, "y": dy, "z": dz,
                                    "xmin": bb[0] * MM_PER_M, "ymin": bb[2] * MM_PER_M, "zmin": bb[4] * MM_PER_M,
                                    "xmax": bb[1] * MM_PER_M, "ymax": bb[3] * MM_PER_M, "zmax": bb[5] * MM_PER_M
                                })
                                res["stock_size"] = self._format_dim_string(dx, dy, dz, False)
                                sel.Clear()
                                return res
                except: continue
            sel.Clear()
        except Exception as e:
            logger.debug(f"  Tier 1 Selection attempt failed: {e}")

        # 3. TIER 3: Context Breaker (Non-destructive isolation)
        # Fixes session corruption by avoiding SaveAs. 
        # Strategy A: File Copy (Robust for saved parts)
        # Strategy B: Copy-Paste AsResult (Fallback for unsaved geometry)
        try:
            temp_dir = str(os.environ.get('TEMP', 'C:\\Temp'))
            ts = int(time.time() * 1000)
            
            # --- Resolve Path and Type ---
            source_path = ""
            try:
                # 1. Try to get path from ReferenceProduct (if it's a Product instance)
                if hasattr(raw_pop, "ReferenceProduct"):
                    print(f"  [DEBUG] Resolving ReferenceProduct for {raw_pop.Name}")
                    ref = raw_pop.ReferenceProduct
                    if hasattr(ref, "Parent"):
                        source_path = ref.Parent.FullName
                        print(f"  [DEBUG] Resolved Reference Path: {source_path}")
                
                # 2. Fallback: Search upwards for any Document parent
                if not source_path or not os.path.exists(source_path):
                    test_obj = raw_pop
                    for _ in range(10):
                        if hasattr(test_obj, "FullName") and (".CAT" in getattr(test_obj, "FullName", "")):
                            source_path = test_obj.FullName
                            break
                        if hasattr(test_obj, "Parent"): test_obj = test_obj.Parent
                        else: break
            except Exception as re:
                print(f"  [DEBUG] Path resolution error: {re}")
            
            iso_doc = None
            temp_file_copy = ""
            
            if source_path and os.path.exists(source_path) and (".CATPart" in source_path or ".CATProduct" in source_path):
                print(f"  [DEBUG] Using File-Copy Isolation for {source_path}")
                try:
                    # Copy to a unique filename so CATIA treats it as a new document
                    ext = ".CATPart" if ".CATPart" in source_path else ".CATProduct"
                    temp_file_copy = os.path.join(temp_dir, f"iso_{ts}{ext}")
                    shutil.copy2(source_path, temp_file_copy)
                    
                    iso_doc = caa.Documents.Open(temp_file_copy)
                    try:
                        # Recursively force Design Mode if product
                        if hasattr(iso_doc, "Product"):
                            iso_doc.Product.ApplyDesignMode()
                        if hasattr(iso_doc, "Part"):
                            iso_doc.Part.Update()
                    except: pass
                except Exception as fe:
                    logger.debug(f"  File-Copy failed: {fe}. Falling back to Copy-Paste.")
            
            if not iso_doc:
                # Fallback to Copy-Paste Isolation
                logger.debug(f"  Fallback: Copy-Paste Isolation for {getattr(raw_pop, 'Name', 'unnamed')}")
                source_doc = active_doc
                if source_doc:
                    source_doc.Activate()
                    target_to_copy = raw_pop
                    
                    sel = source_doc.Selection
                    sel.Clear()
                    sel.Add(target_to_copy)
                    try:
                        sel.Copy()
                        logger.debug("  Source Copy complete.")
                        
                        iso_doc = caa.Documents.Add("Part")
                        iso_doc.Activate()
                        iso_part = iso_doc.Part
                        iso_sel = iso_doc.Selection
                        
                        iso_sel.Clear()
                        iso_sel.Add(iso_part)
                        
                        paste_success = False
                        for p_mode in ["AsResult", "AsResultWithLink", ""]:
                            try:
                                if p_mode: iso_sel.PasteSpecial(p_mode)
                                else: iso_sel.Paste()
                                logger.debug(f"  Paste '{p_mode or 'Default'}' success.")
                                paste_success = True
                                break
                            except: continue
                        
                        if paste_success:
                            iso_part.Update()
                            iso_sel.Clear()
                            try:
                                iso_sel.Search("Type=Body,all")
                                if iso_sel.Count == 0:
                                    iso_sel.Search("Type=*,all")
                            except: pass
                        else:
                            logger.error("  All paste strategies failed.")
                    except Exception as ce:
                        logger.error(f"  Copy-Paste flow failed: {ce}")
            
            if not iso_doc:
                 logger.error("  Context Breaker failed to isolate document.")
                 return self._get_fallback_bbox()

            # --- Extract and Measure ---
            temp_stl = os.path.join(temp_dir, f"measure_{ts}.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            
            try:
                # Use Targeted search to find ANY triangulatable geometry
                iso_doc.Activate()
                iso_sel = iso_doc.Selection
                print(f"  [DEBUG] Isolated Doc: {getattr(iso_doc, 'Name', 'N/A')} ({getattr(iso_doc, 'FullName', 'N/A')})")
                
                # Check Design Mode recursively
                try:
                    if hasattr(iso_doc, "Product"):
                        iso_doc.Product.ApplyDesignMode()
                except: pass
                
                # Try document-level export first
                try: 
                    iso_doc.ExportData(temp_stl, "stl")
                    if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                        print(f"  [DEBUG] Document-level STL success. Size: {os.path.getsize(temp_stl)}")
                except Exception as de:
                    print(f"  [DEBUG] Document-level export failed: {de}")

                if not os.path.exists(temp_stl) or os.path.getsize(temp_stl) <= 100:
                    # Preferred selection for Parts
                    if hasattr(iso_doc, "Part"):
                        try:
                            iso_sel.Clear()
                            iso_sel.Add(iso_doc.Part.MainBody)
                            try: iso_sel.VisProperties.SetShow(0)
                            except: pass
                            iso_sel.ExportData(temp_stl, "stl")
                            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                                print(f"  [DEBUG] Part MainBody STL success. Size: {os.path.getsize(temp_stl)}")
                        except Exception as pe:
                            print(f"  [DEBUG] Part MainBody export failed: {pe}")

                if not os.path.exists(temp_stl) or os.path.getsize(temp_stl) <= 100:
                    queries = ["Type=Face,all", "Type=Surface,all", "Type=Body,all"]
                    for q in queries:
                        try:
                            iso_sel.Clear()
                            iso_sel.Search(f"{q} & Vis=Visible")
                            if iso_sel.Count > 0:
                                iso_sel.ExportData(temp_stl, "stl")
                                if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                                    print(f"  [DEBUG] Selection STL ({q}) success. Size: {os.path.getsize(temp_stl)}")
                                    break
                        except: continue
            except Exception as ee:
                logger.error(f"  STL export fatal error: {ee}")
                print(f"  [DEBUG] STL export fatal error: {ee}")
            
            result = None
            if os.path.exists(temp_stl):
                size = os.path.getsize(temp_stl)
                logger.debug(f"  STL file size: {size} bytes")
                if size > 100:
                    result = self._parse_stl_manual(temp_stl)
            
            # --- Cleanup ---
            if iso_doc:
                try: iso_doc.Close()
                except: pass
            
            if temp_file_copy and os.path.exists(temp_file_copy):
                try: os.remove(temp_file_copy)
                except: pass
            
            if result:
                dx, dy, dz = result["x"], result["y"], result["z"]
                result["stock_size"] = self._format_dim_string(dx, dy, dz, False)
                print(f"  [DEBUG] Context Breaker Success: {result['stock_size']}")
                return result
            else:
                print("  [DEBUG] Context Breaker failed to produce measurable STL.")

        except Exception as e:
            print(f"  [DEBUG] Context Breaker fatal error: {e}")
            logger.error(f"GeometryService: Context Breaker fatal error: {e}")
        finally:
            if 'iso_doc' in locals() and iso_doc:
                try: iso_doc.Close()
                except: pass
            if 'temp_file_copy' in locals() and temp_file_copy and os.path.exists(temp_file_copy):
                try: os.remove(temp_file_copy)
                except: pass
            if 'temp_stl' in locals() and temp_stl and os.path.exists(temp_stl):
                try: os.remove(temp_stl)
                except: pass

        return self._get_fallback_bbox()

    def _get_fallback_bbox(self) -> Dict[str, Any]:
        """Returns a 'Not Measurable' fallback when all strategies fail."""
        return {"x": 0.0, "y": 0.0, "z": 0.0, "stock_size": "Not Measurable"}

    def _resolve_document(self, obj: Any) -> Any:
        """Helper to find the parent Document of any COM object."""
        try:
            curr = obj
            for _ in range(10):
                if hasattr(curr, "FullName") and ("Document" in str(type(curr)) or hasattr(curr, "SaveAs")):
                    return curr
                curr = getattr(curr, "Parent", None)
                if not curr: break
        except: pass
        return None

    def _parse_stl_manual(self, stl_path: str) -> Dict[str, Any] | None:
        """Parses STL ASCII vertices to find AABB extents."""
        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        found = False
        try:
            with open(stl_path, 'r') as f:
                for line in f:
                    if "vertex" in line.lower():
                        pts = line.split()
                        if len(pts) >= 4:
                            x, y, z = float(pts[1]), float(pts[2]), float(pts[3])
                            xmin, ymin, zmin = min(xmin, x), min(ymin, y), min(zmin, z)
                            xmax, ymax, zmax = max(xmax, x), max(ymax, y), max(zmax, z)
                            found = True
            if not found or xmin == float('inf'): return None
            # Explicitly cast to float to avoid lint errors
            f_xmin, f_ymin, f_zmin = float(xmin), float(ymin), float(zmin)
            f_xmax, f_ymax, f_zmax = float(xmax), float(ymax), float(zmax)
            return self._round_bbox({
                "x": f_xmax - f_xmin, "y": f_ymax - f_ymin, "z": f_zmax - f_zmin,
                "xmin": f_xmin, "ymin": f_ymin, "zmin": f_zmin,
                "xmax": f_xmax, "ymax": f_ymax, "zmax": f_zmax
            })
        except: return None

    def get_product_bounding_box(self, product: Any) -> Dict[str, Any]:
        """Assembly envelope: union of child bounding boxes."""
        return self._get_children_union_bbox(product)

    def _get_children_union_bbox(self, com_prod: Any, depth: int = 0, max_depth: int = 8) -> Dict[str, Any]:
        if depth > max_depth:
            return self._get_fallback_bbox()

        global_min = [float('inf')] * 3
        global_max = [float('-inf')] * 3
        found = False

        try:
            # If leaf part
            try:
                ref_prod = com_prod.ReferenceProduct
                if ref_prod:
                    ref_doc = ref_prod.Parent
                    if hasattr(ref_doc, "Part"):
                        return self.get_bounding_box(ref_doc.Part)
            except: pass

            count = 0
            try: count = int(com_prod.Products.Count)
            except: pass

            for i in range(1, int(count) + 1):
                child = com_prod.Products.Item(i)
                try:
                    cbox = self._get_children_union_bbox(child, depth + 1, max_depth)
                    if cbox and float(cbox.get("x", 0)) > 0.1:
                        found = True
                        for idx, axis in enumerate(["x", "y", "z"]):
                            global_min[idx] = min(global_min[idx], float(cbox.get(f"{axis}min", 0)))
                            global_max[idx] = max(global_max[idx], float(cbox.get(f"{axis}max", cbox[axis])))
                except: continue
        except Exception: pass

        if not found: return self._get_fallback_bbox()
        
        dx, dy, dz = global_max[0]-global_min[0], global_max[1]-global_min[1], global_max[2]-global_min[2]
        res = self._round_bbox({
            "x": dx, "y": dy, "z": dz,
            "xmin": global_min[0], "ymin": global_min[1], "zmin": global_min[2],
            "xmax": global_max[0], "ymax": global_max[1], "zmax": global_max[2]
        })
        res["stock_size"] = f"{res['x']} x {res['y']} x {res['z']}"
        return res

    def _round_bbox(self, bbox: Dict[str, Any]) -> Dict[str, Any]:
        """Utility to round all numeric values in a bbox dictionary."""
        rounded = {}
        for k, v in bbox.items():
            if isinstance(v, (int, float)):
                rounded[k] = round(float(v), 2)
            else:
                rounded[k] = v
        return rounded

    def _format_dim_string(self, dx: float, dy: float, dz: float, is_round: bool) -> str:
        """Standardized dimension string with DIA support."""
        if is_round:
            f_dx, f_dy, f_dz = float(dx), float(dy), float(dz)
            diam = max(round(f_dx, 2), round(f_dy, 2))
            length = round(f_dz, 2)
            return f"DIA {diam} x {length}"
        dx_val = round(float(dx), 2)
        dy_val = round(float(dy), 2)
        dz_val = round(float(dz), 2)
        return f"{dx_val} x {dy_val} x {dz_val}"

    def _is_cylindrical(self, part: Any, spa: Any) -> bool:
        """Inspects surfaces to see if the part is primarily cylindrical (round)."""
        try:
            body = self._get_com(part.MainBody)
            if self._check_faces_for_cylinder(body.Faces, spa):
                return True
        except: pass
        
        try:
            for i in range(1, int(part.HybridBodies.Count) + 1):
                try:
                    hb = part.HybridBodies.Item(i)
                    if self._check_faces_for_cylinder(hb.Faces, spa):
                        return True
                except: continue
        except: pass
        return False

    def _check_faces_for_cylinder(self, faces: Any, spa: Any) -> bool:
        """Helper to scan a collection of faces for cylindrical geometry."""
        try:
            check_count = min(faces.Count, 10)
            for i in range(1, check_count + 1):
                try:
                    f = faces.Item(i)
                    m = spa.GetMeasurable(f)
                    name = str(m.GeometryName).lower()
                    if "cylinder" in name or "cylindrical" in name:
                        return True
                except: continue
        except: pass
        return False

    # Removed duplicate _get_fallback_bbox

geometry_service = GeometryService()
