"""
llm_engine.py — LLM API client, prompt assembly, and code extraction.

Handles the core intelligence loop:
1. Assembles user query with Spec Tree context.
2. Calls LLM (OpenAI/Anthropic/Google Gemini).
3. Parses the response for python blocks to extract pycatia scripts.
"""

import re
import logging
from typing import Tuple, Optional
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai

from app.config import settings

from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

class LLMEngine:
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
        
        if settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)
        # We don't initialize gemini_model here to ensure LLM_MODEL changes in .env are picked up in dev mode

    def get_completion(self, user_msg: str, tree_context: dict, tagged_node: Optional[dict] = None, history: Optional[list] = None) -> Tuple[str, Optional[str]]:
        """
        Sends prompt to LLM and returns (natural_language_reply, extracted_code).
        """
        # Prepare history context - only send role and content to avoid token bloat
        formatted_history = []
        if history:
            for msg in history:
                if msg.get("role") and msg.get("content"):
                    role = "assistant" if msg["role"] == "ai" else msg["role"]
                    formatted_history.append({"role": role, "content": msg["content"]})

        # Pull reinforced knowledge from memory
        memory_context = memory_service.get_context_for_prompt()

        system_prompt = f"""You are a CADMation AI Copilot, a senior expert in Sheet Metal Die Design for CATIA V5.
You serve as a guide for fresh designers and a productivity pro tool for experienced designers.

{memory_context}

TAGGED NODE (User Selection):
{tagged_node if tagged_node else "None"}

SHEET METAL DESIGN PRINCIPLES:
1. Minimum Bend Radius: Default to 1x material thickness (T). 
2. Hole Proximity: Minimum distance from a bend to a hole edge: 2T + Bend Radius.
3. Punch Clearance: Ensure standard clearance (typically 10% of T) is maintained between punch and die.
4. Bounding Box: Always consider stock size (Bounding Box) for raw material planning in BOMs.

PRO TOOL CAPABILITIES:
- You have access to a standard database of SHCS (Socket Head Cap Screws) and Dowels (M6, M8, M10, M12).
- You can automatically create drilling and counterbore features by generating pycatia scripts.
- You can generate BOMs by studying the tree's Mass and Dimensions properties.
- **2D Drafting**: Use the `DraftingService` for all drawing requests. 
  **MANDATORY CODE FOR DRAFTING**: 
  ```python
  from app.services.drafting_service import drafting_service
  res = drafting_service.create_automated_drawing(part_name='PART_NAME_HERE')
  print(res.get('message', res.get('error')))
  ```
  DO NOT write custom pycatia scripts for creating views or sheets; always use this service.

NAVIGATION & EXECUTION RULES (MANDATORY):
- Active doc: `doc = caa.active_document`.
- ROOT CONTEXT: If active document is `.CATProduct`, use `doc.product`. If `.CATDrawing`, it has NO product. 
- AVOID ERRORS: Never access `.product` or `.part` on a `DrawingDocument`.
- GET PART FROM PRODUCT: Use `target_part = get_part_from_component(comp)` for component operations.
- LIBRARIES: ONLY use `from pycatia import catia`.
- DESIGN INTENT: When asked to modify, check parameters first. Use `abs(val - target) < 0.1` for matching.
- LOGGING: Every major step MUST be printed for transparency.
- UPDATE: Always call `part.update()` and `doc.product.update()` after modifications.

SPECIFICATION TREE CONTEXT (JSON):
{tree_context}

Format your response:
1. Briefly explain your design reasoning or the rule applied.
2. Provide the `python` script to execute the change.
3. Summarize the outcome.
"""

        try:
            if settings.llm_provider == "openai" and self.openai_client:
                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(formatted_history)
                messages.append({"role": "user", "content": user_msg})
                
                response = self.openai_client.chat.completions.create(
                    model=settings.llm_model,
                    messages=messages
                )
                raw_reply = response.choices[0].message.content
            elif settings.llm_provider == "anthropic" and self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model=settings.llm_model,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=formatted_history + [{"role": "user", "content": user_msg}]
                )
                raw_reply = response.content[0].text
            elif settings.llm_provider == "google" and settings.google_api_key:
                gemini_model = genai.GenerativeModel(settings.llm_model)
                # For Gemini, we'll concatenate history for simplicity as it's often used with generate_content
                history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in formatted_history])
                full_prompt = system_prompt + "\n\nCHAT HISTORY:\n" + history_text + "\n\nUSER REQUEST: " + user_msg
                response = gemini_model.generate_content(full_prompt)
                raw_reply = response.text
            else:
                return f"LLM Provider '{settings.llm_provider}' not configured or missing API key.", None

            # Extract code and natural language
            reply, code = self._parse_response(raw_reply)
            return reply, code

        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return f"Error communicating with AI: {str(e)}", None

    def _parse_response(self, text: str) -> Tuple[str, Optional[str]]:
        """Splits response into explanation and extracted bash script."""
        code_blocks = re.findall(r"```python\n(.*?)\n```", text, re.DOTALL)
        code = code_blocks[0] if code_blocks else None
        
        # Strip code blocks from reply for a cleaner UI
        clean_reply = re.sub(r"```python\n.*?\n```", "", text, flags=re.DOTALL).strip()
        
        return clean_reply, code

# Singleton
llm_engine = LLMEngine()
