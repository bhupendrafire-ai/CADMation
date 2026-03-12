"""
Chat endpoint — the core AI interaction hub.

1. Extracts current CATIA tree state.
2. Assembles prompt and calls LLM.
3. Executes returned pycatia code on the live session.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.services.catia_bridge import catia_bridge
from app.services.tree_extractor import tree_extractor
from app.services.llm_engine import llm_engine
import logging
from pycatia.mec_mod_interfaces.part import Part

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = []
    include_tree: bool = True
    tagged_node: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    code: Optional[str] = None
    executed: bool = False
    error: Optional[str] = None
    output: Optional[str] = None


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # 1. Get Tree Context
    tree_context = {}
    if request.include_tree:
        tree_context = tree_extractor.get_full_tree() or {}

    # 2. Get AI Completion (Passing history)
    reply, code = llm_engine.get_completion(
        request.message, 
        tree_context, 
        request.tagged_node,
        history=request.history
    )

    # 3. Secure Execution (if code is returned)
    executed = False
    exec_error = None
    
    if code:
        import io
        import contextlib
        
        caa = catia_bridge.get_application()
        if caa:
            stdout_capture = io.StringIO()
            try:
                # Prepare execution context
                doc = caa.active_document
                
                def get_part_from_component(component):
                    """Helper to safely jump from a Product Component to its Part geometry."""
                    if component is None:
                        return None
                    try:
                        # Ensure we have the pycatia object
                        from pycatia.product_structure_interfaces.product import Product as PyProduct
                        if not isinstance(component, PyProduct):
                            # Try to wrap it if it's COM
                            try:
                                component = PyProduct(component)
                            except: pass

                        # Try drilling via ReferenceProduct -> Parent -> Part
                        com_obj = component.com_object
                        ref_prod = com_obj.ReferenceProduct
                        parent_doc = ref_prod.Parent
                        
                        # Return the wrapped Part object
                        return Part(parent_doc.Part)
                    except Exception as e:
                        try:
                            # Fallback: maybe it's already a Part document?
                            return Part(component.com_object.Part)
                        except:
                            print(f"DEBUG: Bridge failed for {getattr(component, 'name', 'Unknown')}: {e}")
                            return None

                # Safely determine if doc has a Part
                active_part = None
                try:
                    if ".CATPart" in doc.name:
                        active_part = doc.part
                except: pass

                exec_globals = {
                    "caa": caa,
                    "doc": doc,
                    "part": active_part,
                    "product": doc.product if ".CATProduct" in doc.name else None,
                    "Part": Part,
                    "get_part_from_component": get_part_from_component
                }
                
                # EXECUTE SCRIPT with output capture
                try:
                    with open("last_executed_script.py", "w") as f:
                        f.write(code)
                except:
                    pass
                    
                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stdout_capture):
                    exec(code, exec_globals)
                
                output_text = ""
                executed = True
                try:
                    output_text = stdout_capture.getvalue()
                    logger.info(f"Execution Output: {output_text}")
                except:
                    pass
            except Exception:
                import traceback
                output_text = ""
                try:
                    output_text = stdout_capture.getvalue()
                except:
                    pass
                exec_error = f"{traceback.format_exc()}\nOutput: {output_text}"
                try:
                    logger.error(f"Execution Error: {exec_error}")
                except:
                    pass
        else:
            exec_error = "CATIA not connected; code could not be executed."

    return ChatResponse(
        reply=reply,
        code=code,
        executed=executed,
        error=exec_error,
        output=output_text if 'output_text' in locals() else None
    )
