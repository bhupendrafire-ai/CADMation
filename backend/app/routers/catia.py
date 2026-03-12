"""
CATIA integration endpoints.

- GET /catia/status  → connection health
- GET /catia/tree    → specification tree JSON (Stub)
"""

from fastapi import APIRouter
from app.services.catia_bridge import catia_bridge

router = APIRouter(prefix="/catia", tags=["CATIA"])


@router.get("/status")
async def catia_status():
    """Check if CATIA V5 is running and accessible via COM."""
    is_connected = catia_bridge.check_connection()
    doc_name = catia_bridge.get_active_document_name() if is_connected else None
    
    return {
        "connected": is_connected,
        "active_document": doc_name
    }


from app.services.tree_extractor import tree_extractor

@router.get("/tree")
async def catia_tree():
    """Extract the active document's specification tree as JSON."""
    tree = tree_extractor.get_full_tree()
    if tree is None:
        return {"error": "No active CATIA session found"}
    return tree
