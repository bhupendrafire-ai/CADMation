"""
CATIA integration endpoints.

- GET /catia/status  → connection health
- GET /catia/tree    → specification tree JSON (Stub)
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.catia_bridge import catia_bridge
import json
import asyncio

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

@router.websocket("/bom/calculate/ws")
async def bom_calculate_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        payload = json.loads(data)
        # payload expected: { "items": [ { "id": "PART_REF", "qty": 5, "instances": [...] }, ... ] }
        selected_items = payload.get("items", [])
        
        if not selected_items:
            await websocket.send_text(json.dumps({"error": "No items selected"}))
            await websocket.close()
            return

        caa = catia_bridge.get_application()
        
        results = []
        total = len(selected_items)
        measurement_cache = {} # Cache bounding boxes by Part Number
        
        for idx, item in enumerate(selected_items):
            # Refresh doc reference in case user switched windows
            doc = caa.ActiveDocument
            
            item_id = item.get("id")
            qty = item.get("qty", 1)
            instance_name = item.get("instanceName") or item.get("instances", [f"{item_id}.1"])[0] 
            
            progress = int(((idx + 1) / total) * 100)
            
            msg = f"Measuring {item_id} (x{qty})..."
            bom_service._log_op(msg)
            await websocket.send_text(json.dumps({"progress": progress, "log": msg}))
            
            # Check cache first
            if item_id in measurement_cache:
                msg = f"-> Using cached data for {item_id}"
                bom_service._log_op(msg)
                await websocket.send_text(json.dumps({"log": msg}))
                bbox = measurement_cache[item_id]
            else:
                # Find and measure
                bbox = {"stock_size": "Unknown"}
                try:
                    obj = None
                    if ".CATPART" in doc.Name.upper():
                        obj = doc
                    else:
                        def find_obj(p, name):
                            p_name = getattr(p, "Name", "")
                            p_pn = ""
                            try: p_pn = p.PartNumber
                            except: pass
                            
                            # Exact Name or Part Number match
                            if p_name == name or p_pn == name: return p
                            # Partial match (heuristic)
                            if name in p_name: return p
                            
                            try:
                                for i in range(1, p.Products.Count + 1):
                                    res = find_obj(p.Products.Item(i), name)
                                    if res: return res
                            except: pass
                            return None
                        
                        # First try exact instance name
                        obj = find_obj(doc.Product, instance_name)
                        if not obj:
                            # Then try part number
                            obj = find_obj(doc.Product, item_id)
                    
                    if obj:
                        msg = f"-> Resolved {item_id} to {obj.Name}. Measuring..."
                        bom_service._log_op(msg)
                        await websocket.send_text(json.dumps({"log": msg}))
                        
                        from app.services.geometry_service import geometry_service
                        bbox = geometry_service.get_bounding_box(obj, fast_mode=False)
                        
                        measurement_cache[item_id] = bbox
                        res_size = bbox.get('stock_size', 'Not Measurable')
                        msg = f"-> Result for {item_id}: {res_size}"
                        
                        if "Fallback" in res_size or "Not Measurable" in res_size:
                            msg = f"-> WARNING: Measurement failed for {item_id} (Resolved to {obj.Name})."
                        
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
            
            results.append({
                "id": idx + 1,
                "name": item_id,
                "partNumber": item_id,
                "instanceName": instance_name,
                "size": bbox.get("stock_size", "Not Measurable"),
                "qty": qty,
                "material": "STEEL",
                "isStd": any(x in item_id.upper() for x in ("MISUMI", "DIN", "ISO", "STANDARD"))
            })
            await asyncio.sleep(0.01)

        bom_service._log_op("BOM Calculation complete.")
        await websocket.send_text(json.dumps({
            "status": "done",
            "results": results,
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
        try:
            await websocket.close()
        except: pass
