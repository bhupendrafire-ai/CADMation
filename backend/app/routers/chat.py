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
from app.services.history_service import history_service
import logging
import re
from pycatia.mec_mod_interfaces.part import Part

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str
    history: Optional[list] = []
    include_tree: bool = True
    tagged_node: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    code: Optional[str] = None
    executed: bool = False
    interactive: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    output: Optional[str] = None


from app.services.skill_service import skill_service

from app.services.memory_service import memory_service

@router.get("/sessions")
def list_sessions():
    return history_service.list_sessions()

@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = history_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

class SessionUpdate(BaseModel):
    messages: list
    name: Optional[str] = None
    last_doc: Optional[str] = None

@router.put("/sessions/{session_id}")
def update_session(session_id: str, update: SessionUpdate):
    history_service.save_session(session_id, update.messages, last_doc=update.last_doc)
    return {"status": "success"}

@router.post("/sessions/new")
def create_session():
    return {"session_id": history_service.create_session()}

@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    # 0. Check for Skill Commands
    if skill_service.is_skill_command(request.message):
        result = skill_service.handle_command(request.message)
        return ChatResponse(
            reply=result.reply,
            interactive=result.interactive
        )
    
    # 0.5 Check for Feedback / Reinforcement
    if request.message == "FEEDBACK_YES":
        try:
            last_ai_msg = request.history[-1]
            content = last_ai_msg.get("content", "")
            code_match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
            if code_match:
                memory_service.save_success(request.history[-2]["content"], code_match.group(1))
            return ChatResponse(reply="✅ Glad it worked! I've added this to my rules for next time.")
        except: return ChatResponse(reply="Memory saved.")

    if request.message == "FEEDBACK_NO":
        caa = catia_bridge.get_application()
        if caa:
            try:
                caa.StartCommand("Undo")
                logger.info("Executed CATIA Undo via feedback request.")
            except: pass
        return ChatResponse(
            reply="❌ I've undone the last action. What went wrong? Please give me feedback so I can try again differently.",
            interactive={"type": "choice", "options": [{"id": "retry", "label": "Try again with new feedback", "primary": True}]}
        )

    # 1. Get Context
    tree_context = tree_extractor.get_full_tree() or {}

    # 2. AI Completion
    reply, code = llm_engine.get_completion(
        request.message, 
        tree_context, 
        request.tagged_node,
        history=request.history
    )

    # 3. Secure Execution
    executed = False
    exec_error = None
    output_text = ""
    
    if code:
        import io, contextlib
        caa = catia_bridge.get_application()
        if caa:
            stdout_capture = io.StringIO()
            try:
                doc = caa.ActiveDocument
                active_part = doc.Part if ".CATPart" in doc.Name else None
                
                # ... helper and globals (Simplified for brevity but logic is the same) ...
                def get_part_from_component(c):
                    from pycatia.product_structure_interfaces.product import Product
                    return Part(Product(c).com_object.ReferenceProduct.Parent.Part)

                globals_ctx = {
                    "caa": caa, "doc": doc, "part": active_part, "Part": Part,
                    "product": doc.Product if ".CATProduct" in doc.Name else None,
                    "get_part_from_component": get_part_from_component
                }
                
                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stdout_capture):
                    exec(code, globals_ctx)
                
                executed = True
                output_text = stdout_capture.getvalue()
            except Exception:
                import traceback
                output_text = stdout_capture.getvalue()
                exec_error = f"{traceback.format_exc()}\nOutput: {output_text}"
        else:
            exec_error = "CATIA not connected."

    # 4. Attach Feedback Prompt
    interactive_feedback = None
    if code or "I've analyzed" in reply:
        interactive_feedback = {
            "type": "choice",
            "title": "Was this response appropriate?",
            "options": [
                {"id": "yes", "label": "Yes, this works", "primary": True, "value": "FEEDBACK_YES"},
                {"id": "no", "label": "No, undo and fix", "primary": False, "value": "FEEDBACK_NO"}
            ]
        }

    res = ChatResponse(
        reply=reply,
        code=code,
        executed=executed,
        error=exec_error,
        output=output_text,
        interactive=interactive_feedback
    )

    # 5. Persist History
    try:
        updated_history = request.history + [
            {"role": "user", "content": request.message},
            {"role": "ai", "content": reply, "interactive": interactive_feedback, "code": code, "executed": executed, "output": output_text}
        ]
        
        # Determine current active document for naming
        active_doc_name = catia_bridge.get_active_document_name()
        
        history_service.save_session(request.session_id, updated_history, last_doc=active_doc_name)
    except Exception as e:
        logger.error(f"Chat: Failed to persist history: {e}")

    return res
