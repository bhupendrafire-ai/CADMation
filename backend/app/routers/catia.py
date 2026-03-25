"""
CATIA integration endpoints.

- GET /catia/status  → connection health
- GET /catia/tree    → specification tree JSON (Stub)
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.catia_bridge import catia_bridge
import json
import logging
import asyncio
import os
import re

# Per-item measurement timeout (seconds); prevents hanging on Rough Stock / CATIA Search
BOM_MEASURE_TIMEOUT = 90

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catia", tags=["CATIA"])


@router.get("/status")
def catia_status():
    """Check if CATIA V5 is running and accessible via COM."""
    is_connected = catia_bridge.check_connection()
    doc_name = catia_bridge.get_active_document_name() if is_connected else None
    
    return {
        "connected": is_connected,
        "active_document": doc_name
    }


from app.services.tree_extractor import tree_extractor

@router.get("/tree")
def catia_tree():
    """Extract the active document's specification tree as JSON."""
    tree = tree_extractor.get_full_tree()
    if tree is None:
        return {"error": "No active CATIA session found"}
    return tree

@router.get("/bom")
def catia_bom():
    """Extract tree with focused properties for BOM generation."""
    # Reuse full tree for now as properties were added to the main extractor
    tree = tree_extractor.get_full_tree(include_props=True)
    if tree is None:
        return {"error": "No active CATIA session found"}
    return tree

from fastapi import Body

from app.services.drafting_service import drafting_service
from app.services.bom_service import bom_service

@router.get("/bom/fast")
def get_bom_fast_list():
    """Returns a lightweight grouped list of visible parts for the 2-step BOM selection flow."""
    try:
        items = bom_service.get_bom_fast_list()
    except Exception as e:
        return {"error": str(e)}
    return {"items": items or []}

@router.get("/bom/items")
def get_bom_items():
    """Returns flat list of BOM items from active CATIA tree for the designer editor."""
    try:
        items = bom_service.get_bom_items()
    except Exception as e:
        return {"error": str(e)}
    return {"items": items or []}

@router.post("/bom/excel")
def generate_excel_bom():
    """Generates an automated Excel BOM from current tree and returns the file path."""
    file_path = bom_service.generate_excel_bom()
    if not file_path:
        return {"error": "Failed to generate Excel BOM"}
    return {"status": "success", "file_path": file_path}

@router.post("/bom/save")
def save_bom_excel(payload: dict = Body(..., embed=False)):
    """Saves BOM from designer-edited items. Body: { items: [...] } or raw array."""
    if isinstance(payload, list):
        items = payload
    else:
        items = payload.get("items", []) if isinstance(payload, dict) else []
    if not items:
        return {"error": "No items provided"}
    file_path = bom_service.save_excel_bom(items)
    if not file_path:
        return {"error": "Failed to save BOM"}
    return {"status": "success", "file_path": file_path}


@router.post("/bom/part-bodies")
def bom_part_bodies(payload: dict = Body(...)):
    """List PartDesign body names per BOM row for the measure-body dropdown."""
    from app.services.geometry_service import geometry_service

    items = payload.get("items") if isinstance(payload, dict) else None
    if not items:
        return {"error": "No items", "results": []}
    caa = catia_bridge.get_application()
    if not caa:
        return {"error": "CATIA not connected", "results": []}
    results = []
    for item in items:
        row_id = item.get("id") or item.get("partNumber")
        instance_name = item.get("instanceName") or ""
        sid = item.get("sourceRowId") or f"{row_id}|{instance_name}"
        entry = {
            "sourceRowId": sid,
            "id": row_id,
            "partNumber": item.get("partNumber") or row_id,
            "instanceName": instance_name,
            "bodies": [],
            "error": None,
        }
        try:
            obj = _resolve_bom_item_object(caa, item)
            if obj is None:
                entry["error"] = "unresolved"
                results.append(entry)
                continue
            part_scope = geometry_service._resolve_to_part(obj)
            bodies = getattr(part_scope, "Bodies", None)
            names = []
            if bodies is not None and bodies.Count > 0:
                names = [bodies.Item(i).Name for i in range(1, bodies.Count + 1)]
            else:
                try:
                    mb = getattr(part_scope, "MainBody", None)
                    if mb is not None:
                        names = [getattr(mb, "Name", None) or "MainBody"]
                except Exception:
                    pass
            if not names:
                entry["error"] = "no_bodies"
                results.append(entry)
                continue
            entry["bodies"] = names
        except Exception as e:
            logger.warning("bom_part_bodies row %s: %s", row_id, e)
            entry["error"] = str(e)
        results.append(entry)
    return {"results": results}


@router.post("/drafting/create")
def create_drawing(part_name: str = None):
    """Triggers the creation of an automated 2D drawing for the active Part."""
    return drafting_service.create_automated_drawing(part_name)

def _resolve_product_for_measure(product, part_number: str, instance_name: str):
    """Resolve to a single instance; never return an assembly when multiple instances of same part exist."""
    try:
        if not hasattr(product, "Products") or product.Products.Count == 0:
            return product
        pn = (getattr(product, "PartNumber", "") or "").strip()
        name = getattr(product, "Name", "") or ""
        if pn == part_number and name == instance_name:
            return product
        first_matching = None
        for i in range(1, product.Products.Count + 1):
            child = product.Products.Item(i)
            try:
                c_pn = (getattr(child, "PartNumber", "") or "").strip()
                c_name = getattr(child, "Name", "") or ""
                if c_pn == part_number:
                    if first_matching is None:
                        first_matching = child
                    if c_name == instance_name or not instance_name:
                        return child
                if hasattr(child, "Products") and child.Products.Count > 0:
                    deeper = _resolve_product_for_measure(child, part_number, instance_name)
                    if deeper is not None:
                        return deeper
            except Exception:
                continue
        return first_matching if first_matching is not None else product
    except Exception:
        return product

def _norm_path(path: str) -> str:
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(path or "")))
    except Exception:
        return (path or "").strip().lower()


def _source_path_plausible_for_item(path: str, item_id: str) -> bool:
    """Avoid binding a BOM row to the wrong CATPart when filenames share no digit group with the part id."""
    try:
        bn = "".join(c for c in os.path.basename(path or "").upper() if c.isalnum())
        for m in re.finditer(r"\d{3,}", (item_id or "").upper()):
            if m.group() not in bn:
                return False
        return True
    except Exception:
        return True


def _is_product_instance(obj) -> bool:
    try:
        return obj is not None and getattr(obj, "Products", None) is not None
    except Exception:
        return False


def _geometry_owner_part_and_doc_norm_fp(obj):
    """Walk parents to the Part that owns Bodies; return (part, norm CATPart FullName)."""
    curr = obj
    for _ in range(24):
        if curr is None:
            return None, None
        try:
            if getattr(curr, "Bodies", None) is not None:
                doc = curr.Parent
                fp = _norm_path(getattr(doc, "FullName", "") or "")
                return curr, fp
        except Exception:
            pass
        try:
            curr = curr.Parent
        except Exception:
            break
    return None, None


def _find_product_instance_for_open_tree(
    caa, part_doc_fp_norm: str, instance_name: str, part_number: str
):
    """Every open CATProduct: collect Product nodes whose linked CATPart path matches; disambiguate by instance name."""
    if not part_doc_fp_norm or not caa:
        return None
    candidates = []

    def walk(prod, depth):
        if depth > 80:
            return
        try:
            ref = prod.ReferenceProduct
            link_doc = ref.Parent
            fp = _norm_path(getattr(link_doc, "FullName", "") or "")
            if fp == part_doc_fp_norm:
                candidates.append(prod)
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
    except Exception:
        return None
    if not candidates:
        return None
    inm = (instance_name or "").strip()
    pnum = (part_number or "").strip()
    if inm:
        for c in candidates:
            if (getattr(c, "Name", "") or "") == inm:
                return c
    if pnum:
        matches_pn = [c for c in candidates if (getattr(c, "PartNumber", "") or "").strip() == pnum]
        if len(matches_pn) == 1:
            return matches_pn[0]
        if len(matches_pn) > 1 and inm:
            for c in matches_pn:
                if (getattr(c, "Name", "") or "") == inm:
                    return c
        if len(matches_pn) > 1:
            return matches_pn[0]
    if len(candidates) == 1:
        return candidates[0]
    return candidates[0]


def _resolve_rough_stock_scope_product(caa, obj, instance_name: str, part_number: str):
    """Rough Stock UI needs a tree Product for Search(...,in); Part/Body from BOM resolution must map back to that instance."""
    if obj is None or not caa:
        return None
    try:
        if _is_product_instance(obj):
            return obj
        _, fp = _geometry_owner_part_and_doc_norm_fp(obj)
        if not fp:
            return None
        return _find_product_instance_for_open_tree(caa, fp, instance_name, part_number)
    except Exception:
        return None


def _resolve_obj_by_source_doc_path(caa, source_doc_path: str):
    """
    Resolve the exact target object using tree-provided sourceDocPath.
    This avoids measuring the wrong instance when part-number search is ambiguous.
    """
    src = _norm_path(source_doc_path)
    if not src:
        return None
    try:
        for i in range(1, caa.Documents.Count + 1):
            d = caa.Documents.Item(i)
            d_path = _norm_path(getattr(d, "FullName", "") or "")
            if d_path != src:
                continue
            try:
                if getattr(d, "Part", None) is not None:
                    return d.Part
            except Exception:
                pass
            try:
                if getattr(d, "Product", None) is not None:
                    return d.Product
            except Exception:
                pass
    except Exception:
        pass
    return None


def _resolve_bom_item_object(caa, item: dict):
    """
    Resolve BOM row to a Part/Product COM object. Order matches run_rough_stock_visible_parts:
    plausible sourceDocPath first, then active CATPart only when path matches (or no path),
    then Part Number search and name fallbacks, last-chance open document by path.
    """
    item_id = item.get("id") or item.get("partNumber") or ""
    instances = item.get("instances") or []
    instance_name = item.get("instanceName") or (instances[0] if instances else None) or (
        f"{item_id}.1" if item_id else ""
    )
    source_doc_path = (item.get("sourceDocPath") or "").strip()
    obj = None
    try:
        doc = caa.ActiveDocument
    except Exception:
        return None
    if doc is None:
        return None

    try:
        if source_doc_path and _source_path_plausible_for_item(source_doc_path, item_id):
            obj = _resolve_obj_by_source_doc_path(caa, source_doc_path)
            if obj is not None:
                return obj

        if ".CATPART" in (getattr(doc, "Name", "") or "").upper():
            try:
                active_fp = _norm_path(getattr(doc, "FullName", "") or "")
            except Exception:
                active_fp = ""
            want_fp = _norm_path(source_doc_path) if source_doc_path else active_fp
            if not source_doc_path or want_fp == active_fp:
                try:
                    obj = doc.Part
                except Exception:
                    obj = doc
                if obj is not None:
                    return obj

        sel = caa.ActiveDocument.Selection
        sel.Clear()
        try:
            sel.Search(f"Product.'Part Number'='{item_id}',all")
            if sel.Count > 0:
                pick = sel.Item(1).Value
                for i in range(1, sel.Count + 1):
                    test_obj = sel.Item(i).Value
                    if getattr(test_obj, "Name", "") == instance_name:
                        pick = test_obj
                        break
                obj = _resolve_product_for_measure(pick, item_id, instance_name)
                if obj is not None:
                    return obj
        except Exception as se:
            logger.warning("BOM resolve Part Number search failed for %s: %s", item_id, se)

        fallbacks = []
        if instance_name:
            fallbacks.append(f"Name='*{instance_name}*',all")
        if item_id:
            fallbacks.append(f"Name='*{item_id}*',all")
        for fq in fallbacks:
            try:
                sel.Clear()
                sel.Search(fq)
                if sel.Count > 0:
                    obj = sel.Item(1).Value
                    obj = _resolve_product_for_measure(obj, item_id, instance_name)
                    if obj is not None:
                        return obj
            except Exception:
                continue

        if obj is None and source_doc_path:
            obj = _resolve_obj_by_source_doc_path(caa, source_doc_path)
    except Exception as e:
        logger.error("_resolve_bom_item_object: %s", e)
        return None
    return obj


def _norm_token(value: str) -> str:
    raw = (value or "").upper()
    out = []
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
    return "".join(out)

def _walk_up_to_body(node):
    curr = node
    for _ in range(20):
        if curr is None:
            return None
        try:
            parent = getattr(curr, "Parent", None)
            if getattr(curr, "Shapes", None) is not None and getattr(parent, "Bodies", None) is not None:
                return curr
        except Exception:
            pass
        try:
            curr = getattr(curr, "Parent", None)
        except Exception:
            return None
    return None

def _resolve_body_in_part(part_obj, part_number: str, instance_name: str):
    """
    Pick a body that best matches the BOM row id/instance inside a shared CATPart.
    Returns (body_object, candidates_list, log_lines).
    """
    logs = []
    try:
        existing_body = _walk_up_to_body(part_obj)
        if existing_body is not None:
            nm = getattr(existing_body, "Name", "?")
            logs.append(f"-> Body resolution: already scoped to body '{nm}'.")
            return existing_body, [], logs

        bodies = getattr(part_obj, "Bodies", None)
        if bodies is None:
            logs.append("-> Body resolution: target has no Bodies collection (not a Part scope).")
            return None, [], logs
        if bodies.Count == 0:
            logs.append("-> Body resolution: Part has zero bodies.")
            return None, [], logs

        all_body_names = []
        for i in range(1, bodies.Count + 1):
            all_body_names.append(bodies.Item(i).Name)

        logs.append(
            f"-> Checking {bodies.Count} bodies in {part_number}: {', '.join(all_body_names)}"
        )

        tokens = []
        for candidate in (part_number, instance_name, (instance_name or "").split(".")[0]):
            t = _norm_token(candidate)
            if t:
                tokens.append(t)

        perfect_matches = []
        for i in range(1, bodies.Count + 1):
            b = bodies.Item(i)
            name = _norm_token(getattr(b, "Name", ""))
            if any(tok == name for tok in tokens):
                perfect_matches.append(b)

        if len(perfect_matches) == 1:
            bn = getattr(perfect_matches[0], "Name", "?")
            logs.append(f"-> Body resolution: single exact name match -> '{bn}'.")
            return perfect_matches[0], [], logs
        if len(perfect_matches) > 1:
            logs.append(
                f"-> Body resolution: {len(perfect_matches)} exact name matches; need disambiguation."
            )

        partial_matches = []
        for i in range(1, bodies.Count + 1):
            b = bodies.Item(i)
            name = _norm_token(getattr(b, "Name", ""))
            if any(tok in name or name in tok for tok in tokens):
                partial_matches.append(b)

        if len(partial_matches) == 1:
            bn = getattr(partial_matches[0], "Name", "?")
            logs.append(f"-> Body resolution: single partial name match -> '{bn}'.")
            return partial_matches[0], [], logs
        if len(partial_matches) > 1:
            logs.append(
                f"-> Body resolution: {len(partial_matches)} partial name matches; user must choose."
            )

        if bodies.Count > 1:
            all_body_names.sort()
            logs.append(
                "-> Body resolution: multiple bodies, no unique BOM match; waiting for user selection."
            )
            return None, all_body_names, logs

        logs.append(f"-> Body resolution: single body -> '{bodies.Item(1).Name}'.")
        return bodies.Item(1), [], logs
    except Exception as e:
        logger.error(f"Error in _resolve_body_in_part: {e}")
        logs.append(f"-> Body resolution error: {e}")
        return None, [], logs


@router.websocket("/bom/calculate/ws")
async def bom_calculate_ws(websocket: WebSocket):
    await websocket.accept()
    cancelled_ref = [False]
    disconnect_task = None
    try:
        data = await websocket.receive_text()
        payload = json.loads(data)
        # payload expected: { "items": [...], "method": "STL" | "ROUGH_STOCK" }
        selected_items = payload.get("items", [])
        method = payload.get("method", "AUTO")
        
        if not selected_items:
            await websocket.send_text(json.dumps({"error": "No items selected"}))
            await websocket.close()
            return

        caa = catia_bridge.get_application()
        # Phase 1: Interactive Rough Stock Check
        rs_window = 0
        if method in ("ROUGH_STOCK", "AUTO"):
            from app.services.rough_stock_service import RoughStockService
            msg = "Please open the 'Rough Stock' dialog in CATIA, select the 'AP_AXIS' Publication (under INPUT PART_01) as the reference, and click 'Confirm Axis Selected' in the chat."
            await websocket.send_text(json.dumps({
                "action": "REQUIRE_AXIS_SELECTION",
                "log": msg
            }))
            # Wait for user confirmation
            try:
                conf_data_raw = await websocket.receive_text()
                conf_data = json.loads(conf_data_raw)
                if conf_data.get("command") == "AXIS_CONFIRMED":
                    # Now try to find the window handle
                    rs_window = RoughStockService.open_rough_stock_dialog(caa)
                    if not rs_window:
                        logger.warning("User confirmed axis but Rough Stock window handle not found.")
                else:
                    logger.warning(f"BOM calculate: received unexpected command: {conf_data.get('command')}")
            except Exception as e:
                logger.error(f"Error waiting for axis confirmation: {e}")

        results = []
        stl_defer_items = []
        total = len(selected_items)
        
        from app.services.geometry_service import geometry_service
        geometry_service.clear_cache()
        measurement_cache = {}
        
        for idx, item in enumerate(selected_items):
            if cancelled_ref[0]:
                break
            
            item_id = item.get("id")
            qty = item.get("qty", 1)
            instances = item.get("instances") or []
            instance_name = item.get("instanceName") or (item.get("instances") or [f"{item_id}.1"])[0]
            
            # MULTI-PART DEFERRAL LOGIC
            # If multiple instances, defer to STL Phase at the end to avoid "clubbing" in Rough Stock
            if method in ("ROUGH_STOCK", "AUTO") and (qty > 1 or len(instances) > 1):
                msg = f"-> Deferring {item_id} (x{qty}) to STL measurement phase..."
                bom_service._log_op(msg)
                await websocket.send_text(json.dumps({"log": msg}))
                stl_defer_items.append(item)
                continue

            progress = int(((idx + 1) / total) * 100)
            msg = f"Measuring {item_id}..."
            bom_service._log_op(msg)
            await websocket.send_text(json.dumps({"progress": progress, "log": msg}))
            
            # --- MEASUREMENT LOGIC ---
            _mb = (item.get("measurementBodyName") or item.get("roughStockBodyName") or "").strip()
            cache_key = f"{item_id}|{instance_name}|{method}|{_mb}"
            if cache_key in measurement_cache:
                msg = f"-> Using cached data for {item_id}"
                bom_service._log_op(msg)
                await websocket.send_text(json.dumps({"log": msg}))
                bbox = measurement_cache[cache_key]
            else:
                # Find and measure
                bbox = {"stock_size": "Unknown"}
                try:
                    obj = _resolve_bom_item_object(caa, item)

                    # Map BOM row to PartDesign body: UI-selected name wins, else auto match, else chat prompt.
                    skip_body_measure = False
                    body_target, candidates, resolve_logs = (None, [], [])
                    try:
                        user_bn = (item.get("measurementBodyName") or item.get("roughStockBodyName") or "").strip()
                        if obj is not None and user_bn and user_bn.lower() not in ("auto", "(auto)"):
                            part_scope = geometry_service._resolve_to_part(obj)
                            bodies = getattr(part_scope, "Bodies", None)
                            if bodies:
                                uu = user_bn.upper()
                                for j in range(1, bodies.Count + 1):
                                    b = bodies.Item(j)
                                    if (getattr(b, "Name", "") or "").upper() == uu:
                                        body_target = b
                                        resolve_logs.append(
                                            f"-> Measure body: using BOM-selector choice '{b.Name}' for {item_id}."
                                        )
                                        break
                                if body_target is None:
                                    resolve_logs.append(
                                        f"-> WARNING: measure body '{user_bn}' not found; auto body rules apply."
                                    )
                        if body_target is None and obj is not None:
                            body_target, candidates, resolve_logs = _resolve_body_in_part(
                                obj, item_id, instance_name
                            )
                        elif body_target is not None:
                            candidates = []
                        for line in resolve_logs:
                            bom_service._log_op(line)
                            await websocket.send_text(json.dumps({"log": line}))
                        needed_body_pick = bool(candidates)
                        if candidates and not cancelled_ref[0]:
                            msg = f"Multiple bodies found in {item_id}. Please select the correct one."
                            await websocket.send_text(json.dumps({
                                "action": "REQUIRE_BODY_SELECTION",
                                "log": msg,
                                "itemId": item_id,
                                "candidates": candidates
                            }))
                            try:
                                sel_data_raw = await websocket.receive_text()
                                sel_data = json.loads(sel_data_raw)
                                if sel_data.get("command") == "BODY_SELECTED":
                                    selected_body_name = sel_data.get("bodyName")
                                    part_pick = geometry_service._resolve_to_part(obj)
                                    bodies = getattr(part_pick, "Bodies", None)
                                    if bodies:
                                        for i in range(1, bodies.Count + 1):
                                            if bodies.Item(i).Name == selected_body_name:
                                                body_target = bodies.Item(i)
                                                break
                                else:
                                    logger.warning(
                                        f"BOM calculate: unexpected command during body selection: {sel_data.get('command')}"
                                    )
                            except Exception as e:
                                logger.error(f"Error waiting for body selection: {e}")

                        skip_body_measure = needed_body_pick and body_target is None
                        if skip_body_measure and not cancelled_ref[0]:
                            msg = (
                                f"-> {item_id}: body selection required but not completed; "
                                "skipping measurement (will not use whole Part)."
                            )
                            bom_service._log_op(msg)
                            await websocket.send_text(json.dumps({"log": msg}))

                        if body_target is not None:
                            obj = body_target
                            msg = f"-> Resolved {item_id} to body {getattr(obj, 'Name', 'Unknown')}."
                            bom_service._log_op(msg)
                            await websocket.send_text(json.dumps({"log": msg}))
                    except Exception as e:
                        logger.error(f"Error resolving body: {e}")

                    if skip_body_measure:
                        pass
                    elif obj:
                        try:
                            resolved_name = getattr(obj, "Name", None) or instance_name
                        except Exception:
                            resolved_name = instance_name
                        msg = f"-> Resolved {item_id} to {resolved_name}. Measuring..."
                        bom_service._log_op(msg)
                        await websocket.send_text(json.dumps({"log": msg}))
                        # NOTE: _resolve_to_part can block on some COM objects; GeometryService resolves internally.
                        try:
                            rs_scope = _resolve_rough_stock_scope_product(
                                caa, obj, instance_name, item_id
                            )
                            bbox = geometry_service.get_bounding_box(
                                obj,
                                method=method,
                                rough_stock_window=rs_window,
                                fast_mode=False,
                                stay_open=True,
                                rough_stock_scope_product=rs_scope,
                            ) or {"stock_size": "Not Measurable"}
                        except Exception as e:
                            msg = f"-> Error measuring {item_id}: {e}"
                            bom_service._log_op(msg)
                            await websocket.send_text(json.dumps({"log": msg}))
                            bbox = {"stock_size": "Not Measurable"}
                        measurement_cache[cache_key] = bbox
                        res_size = bbox.get('stock_size', 'Not Measurable')
                        msg = f"-> Result for {item_id}: {res_size}"
                        if "Fallback" in res_size or "Not Measurable" in res_size:
                            msg = f"-> WARNING: Measurement failed for {item_id} (Resolved to {resolved_name})."
                        bom_service._log_op(msg)
                        await websocket.send_text(json.dumps({"log": msg}))
                    else:
                        msg = f"-> WARNING: Could not resolve {item_id} in tree."
                        bom_service._log_op(msg)
                        await websocket.send_text(json.dumps({"log": msg}))

                except Exception as e:
                    msg = f"-> Error measuring {item_id}: {str(e)}"
                    bom_service._log_op(msg)
                    await websocket.send_text(json.dumps({"log": msg}))
                    bbox = {"stock_size": "Not Measurable"}
            
            measured_row = bom_service.build_measured_row(
                {
                    **item,
                    "id": idx + 1,
                    "name": item_id,
                    "partNumber": item.get("partNumber", item_id),
                    "instanceName": instance_name,
                    "qty": qty,
                    "instances": instances,
                },
                bbox,
                method,
            )
            results.append(measured_row)
            await asyncio.sleep(0.01)

        # Phase 2: Deferred STL Measurements
        if stl_defer_items and not cancelled_ref[0]:
            msg = f"Starting STL measurement for {len(stl_defer_items)} deferred items..."
            bom_service._log_op(msg)
            await websocket.send_text(json.dumps({"log": msg}))
            
            for idx, item in enumerate(stl_defer_items):
                if cancelled_ref[0]: break
                item_id = item.get("id")
                qty = item.get("qty", 1)
                instances = item.get("instances") or []
                instance_name = item.get("instanceName") or (item.get("instances") or [f"{item_id}.1"])[0]

                msg = f"STL Measuring {item_id} (x{qty})..."
                bom_service._log_op(msg)
                await websocket.send_text(json.dumps({"log": msg}))
                
                _mb_stl = (item.get("measurementBodyName") or item.get("roughStockBodyName") or "").strip()
                cache_key = f"{item_id}|{instance_name}|STL|{_mb_stl}"
                if cache_key in measurement_cache:
                    msg = f"-> Using cached data for {item_id}"
                    bom_service._log_op(msg)
                    await websocket.send_text(json.dumps({"log": msg}))
                    bbox = measurement_cache[cache_key]
                else:
                    bbox = {"stock_size": "Not Measurable"}
                    try:
                        obj = _resolve_bom_item_object(caa, item)

                        skip_body_measure = False
                        body_target, candidates, resolve_logs = (None, [], [])
                        try:
                            user_bn = (item.get("measurementBodyName") or item.get("roughStockBodyName") or "").strip()
                            if obj is not None and user_bn and user_bn.lower() not in ("auto", "(auto)"):
                                part_scope = geometry_service._resolve_to_part(obj)
                                bodies = getattr(part_scope, "Bodies", None)
                                if bodies:
                                    uu = user_bn.upper()
                                    for j in range(1, bodies.Count + 1):
                                        b = bodies.Item(j)
                                        if (getattr(b, "Name", "") or "").upper() == uu:
                                            body_target = b
                                            resolve_logs.append(
                                                f"-> Measure body (STL): using BOM-selector choice '{b.Name}' for {item_id}."
                                            )
                                            break
                                    if body_target is None:
                                        resolve_logs.append(
                                            f"-> WARNING: measure body '{user_bn}' not found (STL); auto body rules apply."
                                        )
                            if body_target is None and obj is not None:
                                body_target, candidates, resolve_logs = _resolve_body_in_part(
                                    obj, item_id, instance_name
                                )
                            elif body_target is not None:
                                candidates = []
                            for line in resolve_logs:
                                bom_service._log_op(line)
                                await websocket.send_text(json.dumps({"log": line}))
                            needed_body_pick = bool(candidates)
                            if candidates and not cancelled_ref[0]:
                                msg = f"Multiple bodies found in {item_id}. Please select the correct one (STL Phase)."
                                await websocket.send_text(json.dumps({
                                    "action": "REQUIRE_BODY_SELECTION",
                                    "log": msg,
                                    "itemId": item_id,
                                    "candidates": candidates
                                }))
                                try:
                                    sel_data_raw = await websocket.receive_text()
                                    sel_data = json.loads(sel_data_raw)
                                    if sel_data.get("command") == "BODY_SELECTED":
                                        selected_body_name = sel_data.get("bodyName")
                                        part_pick = geometry_service._resolve_to_part(obj)
                                        bodies = getattr(part_pick, "Bodies", None)
                                        if bodies:
                                            for i in range(1, bodies.Count + 1):
                                                if bodies.Item(i).Name == selected_body_name:
                                                    body_target = bodies.Item(i)
                                                    break
                                    else:
                                        logger.warning(
                                            f"BOM calculate (STL): unexpected command during body selection: {sel_data.get('command')}"
                                        )
                                except Exception as e:
                                    logger.error(f"Error waiting for body selection (STL): {e}")

                            skip_body_measure = needed_body_pick and body_target is None
                            if skip_body_measure and not cancelled_ref[0]:
                                msg = (
                                    f"-> {item_id} (STL): body selection required but not completed; "
                                    "skipping measurement (will not use whole Part)."
                                )
                                bom_service._log_op(msg)
                                await websocket.send_text(json.dumps({"log": msg}))

                            if body_target is not None:
                                obj = body_target
                                msg = f"-> Resolved {item_id} to body {getattr(obj, 'Name', 'Unknown')}."
                                bom_service._log_op(msg)
                                await websocket.send_text(json.dumps({"log": msg}))
                        except Exception as e:
                            logger.error(f"Error resolving body (STL): {e}")

                        if skip_body_measure:
                            pass
                        elif obj:
                            try:
                                resolved_name = getattr(obj, "Name", None) or instance_name
                            except Exception:
                                resolved_name = instance_name
                            msg = f"-> Resolved {item_id} to {resolved_name}. Measuring (STL)..."
                            bom_service._log_op(msg)
                            await websocket.send_text(json.dumps({"log": msg}))
                            bbox = geometry_service.get_bounding_box(obj, method="STL", fast_mode=False, stay_open=True) or {"stock_size": "Not Measurable"}
                            measurement_cache[cache_key] = bbox
                            res_size = bbox.get('stock_size', 'Not Measurable')
                            msg = f"-> Result for {item_id} (STL): {res_size}"
                            if "Fallback" in res_size or "Not Measurable" in res_size:
                                msg = f"-> WARNING: Measurement failed for {item_id} (Resolved to {resolved_name})."
                            bom_service._log_op(msg)
                            await websocket.send_text(json.dumps({"log": msg}))
                        else:
                            msg = f"-> WARNING: Could not resolve {item_id} in tree for STL measurement."
                            bom_service._log_op(msg)
                            await websocket.send_text(json.dumps({"log": msg}))
                    except Exception as e:
                        msg = f"-> Error measuring {item_id} (STL): {str(e)}"
                        bom_service._log_op(msg)
                        await websocket.send_text(json.dumps({"log": msg}))
                        bbox = {"stock_size": "Not Measurable"}
                
                measured_row = bom_service.build_measured_row(
                    {
                        **item,
                        "id": idx + 1 + total, # Adjust ID for deferred items if needed, or keep original
                        "name": item_id,
                        "partNumber": item.get("partNumber", item_id),
                        "instanceName": instance_name,
                        "qty": qty,
                        "instances": instances,
                    },
                    bbox,
                    "STL",
                )
                results.append(measured_row)
                await asyncio.sleep(0.01)

        # Close Rough Stock if we opened it
        if rs_window:
            from app.services.rough_stock_service import RoughStockService
            RoughStockService.close_window()

        bom_service._log_op("BOM Calculation complete." if not cancelled_ref[0] else "BOM calculation cancelled by client.")
        if not cancelled_ref[0]:
            await websocket.send_text(json.dumps({
                "status": "done",
                "results": results,
                "retryCandidates": [],
                "log": "Calculation complete! Finalizing results..."
            }))
        
    except WebSocketDisconnect:
        logger.info("BOM calculation websocket disconnected.")
    except Exception as e:
        logger.error(f"WS Error: {e}")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except: pass
    finally:
        cancelled_ref[0] = True
        try:
            from app.services.rough_stock_service import RoughStockService
            RoughStockService.close_window()
        except: pass
        try:
            await websocket.close()
        except Exception:
            pass
