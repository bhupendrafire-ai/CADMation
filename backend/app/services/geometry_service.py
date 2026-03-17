import logging
import math
import os
import shutil
import time
from typing import Dict, Any, List
from app.services.catia_bridge import catia_bridge
from app.services.bom_schema import build_measurement_payload
from app.services.rough_stock_service import RoughStockService

logger = logging.getLogger(__name__)

# CATIA SPA GetBoundaryBox returns meters; we report mm
MM_PER_M = 1000.0

# Names of bodies to ignore (typical construction geometry in die design)
IGNORE_BODY_KEYWORDS = ["STOCK", "BOUNDING", "ENVELOPE", "BOX", "CONSTRUCTION", "AXIS", "WIRE", "SURFACE"]

class GeometryService:
    def __init__(self):
        # Session-wide cache to avoid redundant measurements
        # Keys: ItemID (PartNumber + InstanceName or object handle)
        self._measurement_cache: Dict[str, Dict[str, Any]] = {}

    def _get_com(self, obj: Any) -> Any:
        try:
            if hasattr(obj, "com_object"): return obj.com_object
            return obj
        except: return obj
    
    def clear_cache(self):
        """Clears the session measurement cache."""
        self._measurement_cache = {}
        logger.info("GeometryService: Measurement cache cleared.")

    def _resolve_to_part(self, obj: Any) -> Any:
        """Resolve a Product to its Part (geometry owner). Avoids measuring assembly as one."""
        try:
            raw = self._get_com(obj)
            if not raw:
                return obj
            start_t = time.time()
            while raw:
                try:
                    if getattr(raw, "Bodies", None) is not None:
                        return raw
                except Exception:
                    pass
                if (time.time() - start_t) > 0.75:
                    # If COM traversal stalls, bail out quickly and let callers handle Product directly.
                    return obj
                ref = getattr(raw, "ReferenceProduct", None)
                if not ref:
                    return raw
                raw = ref
            return obj
        except Exception:
            return obj

    def get_bounding_box(self, part_or_product: Any, method: str = "AUTO", fast_mode: bool = False, stay_open: bool = False) -> Dict[str, Any]:
        """Calculates the bounding box of a Part or Product using multiple Tiers.
        Three-Tier Measurement Strategy:
        1. Tier 0: Rough Stock Scraper (Method=ROUGH_STOCK or AUTO)
        2. Tier 1: Direct SPA (Fastest fallback)
        3. Tier 2: Copy-Paste Flattening (Nuclear STL)
        """
        raw_input = self._get_com(part_or_product)
        if not raw_input:
            return self._get_fallback_bbox()
        # Resolve Product to its Part so we never measure whole assembly as one part
        raw_pop = self._resolve_to_part(raw_input)
            
        # 0. Cache Check
        cache_key = ""
        try:
            # Try to identify by Name (unique in session usually) or PartNumber + Name
            obj_name = getattr(raw_pop, "Name", "Unknown")
            pn = getattr(raw_pop, "PartNumber", "")
            cache_key = f"{pn}_{obj_name}_{method}" if pn else f"{obj_name}_{method}"
            
            if cache_key in self._measurement_cache:
                logger.debug(f"  Cache Hit for {cache_key}")
                return self._measurement_cache[cache_key]
        except: pass

        logger.info(f"GeometryService: get_bounding_box for {getattr(raw_pop, 'Name', 'Unknown')} (Method={method})")
        
        caa = self._get_com(catia_bridge.get_application())
        if not caa: 
            return self._get_fallback_bbox()
        
        # Keep using the resolved raw_pop; re-reading part_or_product can reintroduce assemblies / blocking COM.

        res = None

        # --- Tier 0: ROUGH STOCK (High Priority, Fast for Assemblies if done as one unit) ---
        if method in ("ROUGH_STOCK", "AUTO"):
            try:
                # Use the resolved object (Product or Part) directly
                target_obj = raw_pop
                dx, dy, dz = RoughStockService.get_rough_stock_dims(caa, target_obj=target_obj, stay_open=stay_open)
                if dx is not None and dx > 0.001:
                    res = self._round_bbox({
                        "x": dx, "y": dy, "z": dz,
                        "xmin": 0, "ymin": 0, "zmin": 0,
                        "xmax": dx, "ymax": dy, "zmax": dz
                    })
                    res.update(build_measurement_payload(dx, dy, dz, "ROUGH_STOCK"))
                    res["method_used"] = "ROUGH_STOCK"
                    logger.info(f"  Tier 0 Rough Stock Success: {res['stock_size']}")
                    if cache_key: self._measurement_cache[cache_key] = res
                    return res
            except Exception as e:
                logger.debug(f"  Tier 0 Rough Stock failed: {e}")
        if method == "ROUGH_STOCK":
            # If we are NOT an assembly, we can't recurse, so we return fallback here.
            # If we ARE an assembly, we should continue to let Tier 0.5 try recursion.
            if not (hasattr(raw_pop, "Products") and raw_pop.Products.Count > 0):
                logger.warning(f"  Strict ROUGH_STOCK mode: failing measurement for {getattr(raw_pop, 'Name', 'Unknown')}")
                return self._get_fallback_bbox()

        # --- Tier 0.5: Assembly Handling (Fallback recursion for SPA or if Top-Level Rough Stock failed) ---
        try:
            if hasattr(raw_pop, "Products") and raw_pop.Products.Count > 0:
                logger.info(f"  Falling back to recursion for assembly: {getattr(raw_pop, 'Name', 'Unknown')}")
                res = self.get_product_bounding_box(raw_pop, method=method)
                if cache_key: self._measurement_cache[cache_key] = res
                return res
        except: pass

        # --- Tier 1: Direct SPA ---
        try:
            res = self._measure_via_spa(caa, raw_pop)
            if res and res["x"] > 0.1:
                res["method_used"] = "SPA"
                res["measurement_confidence"] = res.get("measurement_confidence", "medium")
                if cache_key:
                    self._measurement_cache[cache_key] = res
                return res
        except: pass

        # --- Tier 2: NUCLEAR STL (Context Breaker) ---
        return self._measure_via_stl_full(caa, raw_pop)

    def _measure_via_spa(self, caa, raw_pop):
        """Direct SPA measurement for fast fallback."""
        try:
            active_doc = self._resolve_document(raw_pop) or caa.ActiveDocument
            spa = active_doc.GetWorkbench("SPAWorkbench")
            sel = active_doc.Selection
            sel.Clear()
            sel.Add(raw_pop)
            
            if sel.Count > 0:
                val = sel.Item(1).Value
                measurable = spa.GetMeasurable(val)
                bb = [0.0] * 6
                bb = measurable.GetBoundaryBox(bb)
                if bb:
                    dx, dy, dz = abs(bb[1]-bb[0]), abs(bb[3]-bb[2]), abs(bb[5]-bb[4])
                    dx, dy, dz = dx * MM_PER_M, dy * MM_PER_M, dz * MM_PER_M
                    result = self._round_bbox({
                        "x": dx, "y": dy, "z": dz,
                        "xmin": bb[0]*MM_PER_M, "ymin": bb[2]*MM_PER_M, "zmin": bb[4]*MM_PER_M,
                        "xmax": bb[1]*MM_PER_M, "ymax": bb[3]*MM_PER_M, "zmax": bb[5]*MM_PER_M
                    })
                    result.update(build_measurement_payload(dx, dy, dz, "SPA"))
                    return result
        except: pass
        return None

    def _measure_via_stl_full(self, caa, raw_pop):
        """Nuclear STL export with Context Isolation."""
        try:
            temp_dir = str(os.environ.get('TEMP', 'C:\\Temp'))
            ts = int(time.time() * 1000)
            
            # Resolve document path
            source_path = ""
            try:
                if hasattr(raw_pop, "ReferenceProduct"):
                    ref = raw_pop.ReferenceProduct
                    if hasattr(ref, "Parent"): source_path = ref.Parent.FullName
                if not source_path:
                    test_obj = raw_pop
                    for _ in range(10):
                        if hasattr(test_obj, "FullName"):
                            source_path = test_obj.FullName
                            break
                        test_obj = getattr(test_obj, "Parent", None)
                        if not test_obj: break
            except: pass

            iso_doc = None
            temp_file_copy = ""
            if source_path and os.path.exists(source_path):
                ext = ".CATPart" if ".CATPart" in source_path else ".CATProduct"
                temp_file_copy = os.path.join(temp_dir, f"iso_{ts}{ext}")
                shutil.copy2(source_path, temp_file_copy)
                iso_doc = caa.Documents.Open(temp_file_copy)
            
            if not iso_doc:
                # Last resort: copy-paste into new part
                iso_doc = caa.Documents.Add("Part")
                sel = caa.ActiveDocument.Selection
                sel.Clear()
                sel.Add(raw_pop)
                sel.Copy()
                iso_doc.Activate()
                iso_doc.Selection.Add(iso_doc.Part)
                iso_doc.Selection.PasteSpecial("AsResult")

            temp_stl = os.path.join(temp_dir, f"measure_{ts}.stl")
            iso_doc.ExportData(temp_stl, "stl")
            
            result = None
            if os.path.exists(temp_stl):
                result = self._parse_stl_manual(temp_stl)
            
            try: iso_doc.Close()
            except: pass
            if temp_file_copy and os.path.exists(temp_file_copy): os.remove(temp_file_copy)
            if os.path.exists(temp_stl): os.remove(temp_stl)

            if result:
                result.update(build_measurement_payload(result["x"], result["y"], result["z"], "STL"))
                result["method_used"] = "STL"
                return result
        except: pass
        return self._get_fallback_bbox()

    def _parse_stl_manual(self, stl_path: str) -> Dict[str, Any] | None:
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
            if not found: return None
            return self._round_bbox({
                "x": xmax - xmin, "y": ymax - ymin, "z": zmax - zmin,
                "xmin": xmin, "ymin": ymin, "zmin": zmin,
                "xmax": xmax, "ymax": ymax, "zmax": zmax
            })
        except: return None

    def _get_reference_part_key(self, child: Any) -> str:
        """Returns a stable key for the reference Part (same part definition = same key)."""
        try:
            ref = getattr(child, "ReferenceProduct", None)
            if ref and hasattr(ref, "Parent"):
                return getattr(ref.Parent, "FullName", "") or ""
            pn = getattr(child, "PartNumber", "") or ""
            name = getattr(child, "Name", "") or ""
            return f"{pn}|{name.split('.')[0]}"
        except Exception:
            return ""

    def get_product_bounding_box(self, product: Any, method: str = "AUTO", stay_open: bool = False) -> Dict[str, Any]:
        global_min, global_max = [float('inf')] * 3, [float('-inf')] * 3
        found = False
        try:
            is_rough = (method in ("ROUGH_STOCK", "AUTO"))
            # One instance per reference Part: multiple quantities of same part → measure once, not union
            seen_ref_keys = set()
            children_to_measure = []
            for i in range(1, product.Products.Count + 1):
                child = product.Products.Item(i)
                ref_key = self._get_reference_part_key(child)
                if ref_key and ref_key in seen_ref_keys:
                    continue
                if ref_key:
                    seen_ref_keys.add(ref_key)
                children_to_measure.append(child)

            for child in children_to_measure:
                cbox = self.get_bounding_box(child, method=method, stay_open=is_rough)
                if cbox and cbox["x"] > 0.1:
                    found = True
                    for idx, axis in enumerate(["x", "y", "z"]):
                        global_min[idx] = min(global_min[idx], cbox.get(f"{axis}min", 0))
                        global_max[idx] = max(global_max[idx], cbox.get(f"{axis}max", cbox[axis]))
            if is_rough and not stay_open:
                RoughStockService.close_window()
        except Exception:
            pass
        if not found:
            return self._get_fallback_bbox()
        dx, dy, dz = global_max[0]-global_min[0], global_max[1]-global_min[1], global_max[2]-global_min[2]
        res = self._round_bbox({"x": dx, "y": dy, "z": dz})
        res.update(build_measurement_payload(dx, dy, dz, method))
        return res

    def _get_fallback_bbox(self) -> Dict[str, Any]:
        return {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "stock_size": "Not Measurable",
            "stockForm": "unknown",
            "sizeKind": "empty",
            "rawDims": [],
            "orderedDims": [],
            "measurement_confidence": "low",
        }

    def _round_bbox(self, bbox: Dict[str, Any]) -> Dict[str, Any]:
        return {k: (round(float(v), 2) if isinstance(v, (int, float)) else v) for k, v in bbox.items()}

    def _format_dim_string(self, dx: float, dy: float, dz: float, is_round: bool) -> str:
        return build_measurement_payload(dx, dy, dz, "")["stock_size"]

    def _resolve_document(self, obj: Any) -> Any:
        curr = obj
        for _ in range(10):
            if hasattr(curr, "FullName") and ("Document" in str(type(curr)) or hasattr(curr, "SaveAs")):
                return curr
            curr = getattr(curr, "Parent", None)
            if not curr: break
        return None

geometry_service = GeometryService()
