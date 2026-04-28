import logging
import math
import os
import shutil
import time
from typing import Dict, Any, List
from app.services.catia_bridge import catia_bridge
from app.services.bom_schema import build_measurement_payload
from app.services.rough_stock_service import RoughStockService
from app.debug_agent_log import agent_ndjson

logger = logging.getLogger(__name__)

# CATIA SPA GetBoundaryBox returns meters; we report mm
MM_PER_M = 1000.0

# Bump when cache key shape changes so stale in-process dict entries cannot serve wrong parts (see debug H1 MAIN_BODY-only keys).
_MEASUREMENT_CACHE_KEY_VER = "rs4"

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

    @staticmethod
    def _same_com_object(a: Any, b: Any) -> bool:
        if a is None or b is None:
            return False
        if a is b:
            return True
        try:
            oa, ob = getattr(a, "_oleobj_", None), getattr(b, "_oleobj_", None)
            return oa is not None and oa == ob
        except Exception:
            return False
    
    def clear_cache(self):
        """Clears the session measurement cache."""
        self._measurement_cache = {}
        logger.info("GeometryService: Measurement cache cleared.")

    def _measurement_cache_key(self, raw_pop: Any, method: str) -> str:
        """Disambiguate Part across CATPart documents; always pass the resolved Part, not a Body (Bodies lack doc path)."""
        obj_name = getattr(raw_pop, "Name", "Unknown")
        pn = (getattr(raw_pop, "PartNumber", None) or "").strip()
        doc_fp = ""
        try:
            doc = getattr(raw_pop, "Parent", None)
            if doc is not None:
                fp = (getattr(doc, "FullName", None) or "").strip()
                if fp:
                    doc_fp = os.path.normcase(os.path.normpath(os.path.abspath(fp)))
        except Exception:
            pass
        parts = [doc_fp, pn, obj_name, method]
        return "::".join(p if p else "-" for p in parts)

    def _rough_stock_dialog_target(self, raw_input: Any, raw_pop: Any) -> Any:
        """Use BOM leaf (e.g. Body) when it resolves to raw_pop Part; do not probe ri.Bodies (CATIA COM is inconsistent)."""
        try:
            ri = self._get_com(raw_input)
            rp = self._get_com(raw_pop)
            if not ri or not rp:
                return raw_pop
            if ri is rp:
                return raw_pop
            resolved_ri = self._resolve_to_part(ri)
            same = resolved_ri is rp
            if not same:
                try:
                    same = (getattr(resolved_ri, "Name", None) or "") == (
                        getattr(rp, "Name", None) or ""
                    )
                except Exception:
                    pass
            if not same:
                return raw_pop
            try:
                if getattr(ri, "ReferenceProduct", None) is not None:
                    return raw_pop
            except Exception:
                pass
            # region agent log
            try:
                agent_ndjson(
                    "H11",
                    "geometry_service._rough_stock_dialog_target",
                    "using BOM leaf under resolved Part",
                    {
                        "leaf_name": getattr(ri, "Name", None),
                        "raw_pop_name": getattr(rp, "Name", None),
                    },
                )
            except Exception:
                pass
            # endregion
            return ri
        except Exception:
            return raw_pop

    def _resolve_to_part(self, obj: Any) -> Any:
        """Resolve to PartDesign Part (owns .Bodies). Assembly Product -> ReferenceProduct.Parent.Part."""
        # Regression guard: keep ReferenceProduct.Parent.Part; see tests/test_part_resolution_contract.py and .cursor/rules/catia-part-resolution-regression.mdc
        try:
            raw = self._get_com(obj)
            if not raw:
                return obj

            def _part_has_bodies(o) -> bool:
                try:
                    return getattr(o, "Bodies", None) is not None
                except Exception:
                    return False

            if _part_has_bodies(raw):
                return raw

            try:
                p = getattr(raw, "Part", None)
                if p is not None and _part_has_bodies(p):
                    return p
            except Exception:
                pass

            # Instance under CATProduct -> linked CATPart's Part (was missing before; Bodies stayed empty on Product).
            try:
                ref = getattr(raw, "ReferenceProduct", None)
                if ref is not None:
                    doc = getattr(ref, "Parent", None)
                    part = getattr(doc, "Part", None) if doc is not None else None
                    if part is not None and _part_has_bodies(part):
                        return part
            except Exception:
                pass

            try:
                par = getattr(raw, "Parent", None)
                for _ in range(30):
                    if par is None:
                        break
                    if _part_has_bodies(par):
                        return par
                    par = getattr(par, "Parent", None)
            except Exception:
                pass

            start_t = time.time()
            cur = raw
            while cur:
                if _part_has_bodies(cur):
                    return cur
                if (time.time() - start_t) > 0.75:
                    break
                ref = getattr(cur, "ReferenceProduct", None)
                if not ref:
                    break
                cur = ref
            return obj
        except Exception:
            return obj

    def _product_instance_holding_part(self, caa: Any, part: Any) -> Any:
        """Open CATProduct docs: Product node whose linked CATPart path + internal Part.Name match (Rough Stock Search ,in)."""
        try:
            part = self._get_com(part)
            pdoc = getattr(part, "Parent", None)
            target_fp = os.path.normcase(
                os.path.normpath(os.path.abspath(getattr(pdoc, "FullName", "") or ""))
            )
            if not target_fp:
                return None
            part_nm = getattr(part, "Name", "") or ""
            found = [None]

            def walk(prod, depth):
                if depth > 80 or found[0] is not None:
                    return
                try:
                    ref = prod.ReferenceProduct
                    link_doc = ref.Parent
                    fp = os.path.normcase(
                        os.path.normpath(os.path.abspath(getattr(link_doc, "FullName", "") or ""))
                    )
                    if fp == target_fp and getattr(link_doc, "Part", None) is not None:
                        if (getattr(link_doc.Part, "Name", "") or "") == part_nm:
                            found[0] = prod
                            return
                except Exception:
                    pass
                try:
                    ch = prod.Products
                    for i in range(1, ch.Count + 1):
                        walk(ch.Item(i), depth + 1)
                except Exception:
                    pass

            try:
                for di in range(1, caa.Documents.Count + 1):
                    d = caa.Documents.Item(di)
                    root = getattr(d, "Product", None)
                    if root is None:
                        continue
                    walk(root, 0)
                    if found[0] is not None:
                        return found[0]
                    found[0] = None
            except Exception:
                pass
            return found[0]
        except Exception:
            return None

    def get_bounding_box(
        self,
        part_or_product: Any,
        method: str = "AUTO",
        rough_stock_window: Any = None,
        fast_mode: bool = False,
        stay_open: bool = False,
        scope_product: Any = None,
        rough_stock_scope_product: Any = None,
    ) -> Dict[str, Any] | None:
        """
        Calculates the bounding box (Stock Size) of a target component.
        Thread Safety: part_or_product can be a string (PartNumber) for local re-resolution.
        """
        caa = catia_bridge.get_application()
        if not caa:
            return None

        # 1. Resolve COM object from name if passed as string (Thread Isolation Path)
        target_obj = part_or_product
        from app.services.tree_extractor import tree_extractor
        
        if isinstance(part_or_product, str):
            target_obj = tree_extractor.find_object_by_name(caa, part_or_product)
            if target_obj is None:
                logger.error(f"GeometryService: Could not find component '{part_or_product}' by name.")
                return None
        
        # 1b. Resolve Scope Product (Marshaling Safety)
        actual_scope = scope_product
        if isinstance(scope_product, str):
            actual_scope = tree_extractor.find_object_by_name(caa, scope_product)
            
        actual_rs_scope = rough_stock_scope_product
        if isinstance(rough_stock_scope_product, str):
            actual_rs_scope = tree_extractor.find_object_by_name(caa, rough_stock_scope_product)

        raw_input = self._get_com(target_obj)
        if not raw_input:
            return self._get_fallback_bbox()
        # STL should preserve instance-level context; ROUGH_STOCK/SPA can resolve to Part.
        if method == "STL":
            raw_pop = raw_input
            try:
                # Active CATPart document should still resolve to Document.Part.
                p = getattr(raw_pop, "Part", None)
                if p is not None:
                    raw_pop = p
            except Exception:
                pass
        else:
            # Resolve Product to its Part so we never measure whole assembly as one part
            raw_pop = self._resolve_to_part(raw_input)

        # region agent log
        try:
            _inp_bodies = getattr(raw_input, "Bodies", None) is not None
            _pop_bodies = getattr(raw_pop, "Bodies", None) is not None
            agent_ndjson(
                "H5",
                "geometry_service.get_bounding_box:after_resolve",
                "raw_input vs raw_pop for non-STL",
                {
                    "method": method,
                    "raw_input_name": getattr(raw_input, "Name", None),
                    "raw_input_is_part_root": _inp_bodies,
                    "raw_pop_name": getattr(raw_pop, "Name", None),
                    "raw_pop_is_part_root": _pop_bodies,
                    "same_object": raw_input is raw_pop,
                },
            )
        except Exception:
            pass
        # endregion

        # BOM passes a PartDesign Body; Rough Stock must measure that Body, not Parent Part (see debug H5).
        rs_dialog_target = self._rough_stock_dialog_target(raw_input, raw_pop)

        # BOM Product instance: Rough Stock on assembly must use Search(...,in) under this node.
        scope_product = rough_stock_scope_product
        if method != "STL" and scope_product is None:
            try:
                ri = raw_input
                if (
                    ri is not None
                    and getattr(ri, "Products", None) is not None
                    and getattr(ri, "ReferenceProduct", None) is not None
                ):
                    scope_product = ri
            except Exception:
                scope_product = None

        # 0. Cache: version prefix drops stale MAIN_BODY-only slots; base key from resolved Part; ::body= when input leaf != part (COM-safe, not `is`).
        cache_key = ""
        try:
            part_for_key = self._resolve_to_part(raw_pop)
            # Resolve hint text early while COM is stable (before any modal dialogs/sweeps)
            cached_hint = ""
            try:
                cached_hint = getattr(rs_dialog_target, "Name", "") or ""
            except Exception:
                try:
                    cached_hint = (getattr(raw_pop, "PartNumber", "") or getattr(raw_pop, "Name", ""))
                except Exception:
                    pass

            cache_key = f"{_MEASUREMENT_CACHE_KEY_VER}::{self._measurement_cache_key(part_for_key, method)}"
            inp_c, pop_c = self._get_com(raw_input), self._get_com(raw_pop)
            if not self._same_com_object(inp_c, pop_c):
                bn = (getattr(rs_dialog_target, "Name", None) or "").strip()
                if bn:
                    cache_key = f"{cache_key}::body={bn}"
            if cache_key in self._measurement_cache:
                # region agent log
                agent_ndjson(
                    "H1",
                    "geometry_service.get_bounding_box:cache_hit",
                    "returning cached bbox",
                    {
                        "cache_key": cache_key,
                        "part_for_key_name": getattr(part_for_key, "Name", None),
                        "stock_size": (self._measurement_cache[cache_key] or {}).get("stock_size"),
                    },
                )
                # endregion
                logger.debug(f"  Cache Hit for {cache_key}")
                return self._measurement_cache[cache_key]
        except Exception:
            pass

        logger.info(f"GeometryService: get_bounding_box for {getattr(raw_pop, 'Name', 'Unknown')} (Method={method})")
        
        caa = self._get_com(catia_bridge.get_application())
        if not caa: 
            return self._get_fallback_bbox()

        if (
            method != "STL"
            and scope_product is None
            and raw_pop is not None
        ):
            try:
                sp = self._product_instance_holding_part(caa, raw_pop)
                if sp is not None:
                    scope_product = sp
                    logger.info(
                        "Rough Stock: inferred Product instance %r for Part (assembly-scoped Search).",
                        getattr(sp, "Name", "?"),
                    )
            except Exception:
                pass
        
        # Keep using the resolved raw_pop; re-reading part_or_product can reintroduce assemblies / blocking COM.

        res = None

        # --- Tier 0: ROUGH STOCK (High Priority, Fast for Assemblies if done as one unit) ---
        if method in ("ROUGH_STOCK", "AUTO"):
            try:
                # 1. Tier 0.1: Interactive Rough Stock (if window provided)
                if rough_stock_window:
                    logger.info(f"Using interactive Rough Stock window: {rough_stock_window}")
                    try:
                        anchor_asm_doc = None
                        if scope_product is not None:
                            try:
                                anchor_asm_doc = caa.ActiveDocument
                            except Exception:
                                pass
                        # region agent log
                        agent_ndjson(
                            "H5",
                            "geometry_service.get_bounding_box:before_measure_dialog",
                            "calling measure_body_in_dialog",
                            {
                                "passing_name": getattr(rs_dialog_target, "Name", None),
                                "raw_input_name": getattr(raw_input, "Name", None),
                                "raw_pop_name": getattr(raw_pop, "Name", None),
                            },
                        )
                        # endregion
                        dx, dy, dz = RoughStockService.measure_body_in_dialog(
                            caa,
                            rs_dialog_target,
                            rough_stock_window,
                            scope_product=actual_scope,
                            anchor_asm_doc=anchor_asm_doc,
                            skip_axis_spa_shortcuts=(rs_dialog_target is not raw_pop),
                            rough_stock_scope_product=actual_rs_scope
                        )
                        if dx is not None:
                            result = build_measurement_payload(
                                dx, dy, dz, "ROUGH_STOCK", hint_text=cached_hint
                            )
                            result["method_used"] = "ROUGH_STOCK_INTERACTIVE"
                            if cache_key: self._measurement_cache[cache_key] = result
                            return result
                    except Exception as e:
                        logger.warning(f"Interactive Rough Stock failed: {e}")
                
                # 1. Tier 0.2: Standard Rough Stock (Scraper) — same body as BOM / Tier 0.1 (not whole Part).
                target_obj = rs_dialog_target
                # region agent log
                try:
                    agent_ndjson(
                        "H10",
                        "geometry_service.get_bounding_box:tier0_2",
                        "non-interactive rough stock target",
                        {
                            "rough_stock_window": int(rough_stock_window or 0),
                            "tier02_target_name": getattr(target_obj, "Name", None),
                            "raw_pop_name": getattr(raw_pop, "Name", None),
                        },
                    )
                except Exception:
                    pass
                # endregion
                _bom_body_leaf = rs_dialog_target is not raw_pop
                # region agent log
                try:
                    agent_ndjson(
                        "H14",
                        "geometry_service.get_bounding_box:tier0_2_spa_policy",
                        "skip axis/world SPA when BOM targets a body leaf",
                        {
                            "bom_specific_body": _bom_body_leaf,
                            "rs_name": getattr(rs_dialog_target, "Name", None),
                            "part_name": getattr(raw_pop, "Name", None),
                        },
                    )
                except Exception:
                    pass
                # endregion
                dx, dy, dz = RoughStockService.get_rough_stock_dims(
                    caa,
                    target_obj=target_obj,
                    stay_open=stay_open,
                    scope_product=scope_product,
                    bom_specific_body=_bom_body_leaf,
                )
                if dx is not None and dx > 0.001:
                    res = self._round_bbox({
                        "x": dx, "y": dy, "z": dz,
                        "xmin": 0, "ymin": 0, "zmin": 0,
                        "xmax": dx, "ymax": dy, "zmax": dz
                    })
                    res.update(build_measurement_payload(dx, dy, dz, "ROUGH_STOCK", hint_text=cached_hint))
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
            res = self._measure_via_spa(caa, rs_dialog_target)
            if res and res["x"] > 0.1:
                res["method_used"] = "SPA"
                res["measurement_confidence"] = res.get("measurement_confidence", "medium")
                if cache_key:
                    self._measurement_cache[cache_key] = res
                return res
        except: pass

        # --- Tier 2: NUCLEAR STL (Context Breaker) ---
        return self._measure_via_stl_full(caa, rs_dialog_target)

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
                    result.update(build_measurement_payload(dx, dy, dz, "SPA", hint_text=getattr(raw_pop, "Name", "")))
                    return result
        except: pass
        return None

    def _measure_via_stl_full(self, caa, raw_pop):
        """Nuclear STL export with Context Isolation."""
        try:
            temp_dir = str(os.environ.get('TEMP', 'C:\\Temp'))
            ts = int(time.time() * 1000)
            is_body_target = False
            try:
                is_body_target = (
                    getattr(raw_pop, "Shapes", None) is not None
                    and getattr(getattr(raw_pop, "Parent", None), "Bodies", None) is not None
                )
            except Exception:
                is_body_target = False
            
            # Resolve document path
            source_path = ""
            if not is_body_target:
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
                result.update(build_measurement_payload(result["x"], result["y"], result["z"], "STL", hint_text=getattr(raw_pop, "Name", "")))
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
        res.update(build_measurement_payload(dx, dy, dz, method, hint_text=getattr(product, "Name", "")))
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
