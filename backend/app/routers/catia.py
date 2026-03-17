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


@router.websocket("/bom/calculate/ws")
async def bom_calculate_ws(websocket: WebSocket):
    await websocket.accept()
    cancelled_ref = [False]
    disconnect_task = None

    async def wait_for_disconnect():
        try:
            while not cancelled_ref[0]:
                await websocket.receive_text()
        except WebSocketDisconnect:
            cancelled_ref[0] = True
            logger.info("BOM calculate: client disconnected (cancel).")

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

        disconnect_task = asyncio.create_task(wait_for_disconnect())
        caa = catia_bridge.get_application()
        
        results = []
        retry_candidates = []
        total = len(selected_items)
        
        from app.services.geometry_service import geometry_service
        geometry_service.clear_cache()
        
        measurement_cache = {}
        
        for idx, item in enumerate(selected_items):
            if cancelled_ref[0]:
                break
            # Refresh doc reference in case user switched windows
            doc = caa.ActiveDocument
            
            item_id = item.get("id")
            qty = item.get("qty", 1)
            instances = item.get("instances") or []
            instance_name = item.get("instanceName") or (item.get("instances") or [f"{item_id}.1"])[0]
            effective_method = method
            if method in ("ROUGH_STOCK", "AUTO") and (qty > 1 or len(instances) > 1):
                effective_method = "STL"
            
            progress = int(((idx + 1) / total) * 100)
            
            msg = f"Measuring {item_id} (x{qty})..."
            bom_service._log_op(msg)
            await websocket.send_text(json.dumps({"progress": progress, "log": msg}))
            
            cache_key = f"{item_id}|{instance_name}|{effective_method}"
            if cache_key in measurement_cache:
                msg = f"-> Using cached data for {item_id}"
                bom_service._log_op(msg)
                await websocket.send_text(json.dumps({"log": msg}))
                bbox = measurement_cache[cache_key]
            else:
                # Find and measure
                bbox = {"stock_size": "Unknown"}
                try:
                    obj = None
                    if ".CATPART" in doc.Name.upper():
                        obj = doc
                    else:
                        sel = caa.ActiveDocument.Selection
                        sel.Clear()
                        try:
                            search_query = f"Product.'Part Number'='{item_id}',all"
                            sel.Search(search_query)
                            if sel.Count > 0:
                                obj = sel.Item(1).Value
                                for i in range(1, sel.Count + 1):
                                    test_obj = sel.Item(i).Value
                                    if test_obj.Name == instance_name:
                                        obj = test_obj
                                        break
                                # If we got an assembly, resolve to the specific part so we don't measure full assembly
                                obj = _resolve_product_for_measure(obj, item_id, instance_name)
                        except Exception as se:
                            logger.warning(f"Search failed for {item_id}: {se}")
                            try:
                                fallback_queries = []
                                if instance_name:
                                    fallback_queries.append(f"Name='*{instance_name}*',all")
                                fallback_queries.append(f"Name='*{item_id}*',all")
                                for search_query in fallback_queries:
                                    sel.Clear()
                                    logger.info(f"Fallback search: {search_query}")
                                    sel.Search(search_query)
                                    if sel.Count > 0:
                                        obj = sel.Item(1).Value
                                        obj = _resolve_product_for_measure(obj, item_id, instance_name)
                                        logger.info(f"Fallback found {sel.Count} items, picked {obj.Name}")
                                        break
                            except Exception as fe:
                                logger.error(f"Fallback search also failed: {fe}")
                    
                    if obj:
                        try:
                            resolved_name = getattr(obj, "Name", None) or instance_name
                        except Exception:
                            resolved_name = instance_name
                        if effective_method != method:
                            msg = (
                                f"-> Grouped duplicates detected for {item_id}; "
                                f"using {effective_method} to avoid combined Rough Stock."
                            )
                            bom_service._log_op(msg)
                            await websocket.send_text(json.dumps({"log": msg}))
                        msg = f"-> Resolved {item_id} to {resolved_name}. Measuring..."
                        bom_service._log_op(msg)
                        await websocket.send_text(json.dumps({"log": msg}))
                        # NOTE: _resolve_to_part can block on some COM objects; GeometryService resolves internally.
                        try:
                            bbox = geometry_service.get_bounding_box(obj, method=effective_method, fast_mode=False) or {"stock_size": "Not Measurable"}
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
                effective_method,
            )
            results.append(measured_row)
            if (
                effective_method == "ROUGH_STOCK"
                and bbox.get("stock_size", "Not Measurable") == "Not Measurable"
            ):
                retry_candidates.append(bom_service.build_retry_candidate(measured_row))
            await asyncio.sleep(0.01)

        bom_service._log_op("BOM Calculation complete." if not cancelled_ref[0] else "BOM calculation cancelled by client.")
        if not cancelled_ref[0]:
            await websocket.send_text(json.dumps({
                "status": "done",
                "results": results,
                "retryCandidates": retry_candidates,
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
        if disconnect_task is not None:
            if disconnect_task.done():
                try:
                    disconnect_task.result()
                except Exception:
                    pass
            else:
                disconnect_task.cancel()
                try:
                    await disconnect_task
                except asyncio.CancelledError:
                    pass
        try:
            await websocket.close()
        except Exception:
            pass
