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

        system_prompt = f"""You are a CATIA V5 AI Copilot specializing in Sheet Metal Die Design.
You have direct access to the user's active CATIA session via the 'pycatia' library.

TAGGED NODE (User Selection):
{tagged_node if tagged_node else "None (User has not tagged a specific node)"}

CURRENT CONTEXT (Specification Tree):
{tree_context}

4. **Interacting with the User**:
   - **CONFIRMATION**: Always describe what you are about to do before doing it.
   - **CLARIFICATION**: If the user's request is ambiguous, ask for details.
   - **NON-DESTRUCTIVE**: Remind the user if an action cannot be undone on imported data.
5. **Navigation & Execution Rules (MANDATORY)**:
    - `doc = caa.active_document`.
    - **ROOT CONTEXT**: If the active document is a `.CATProduct`, `doc.part` DOES NOT EXIST. Use `doc.product` for assembly operations.
    - **GET PART FROM PRODUCT**: You MUST use the provided `target_part = get_part_from_component(comp)` for any operations inside a component.
    - **DO NOT REDEFINE HELPERS**: NEVER redefine `get_part_from_component`. Use the one in context.
   - **CRITICAL PROHIBITION**: NEVER use `part.sketches` or `comp.get_part()`.
   - **AMBIGUITY DETECTION**: If you find multiple matches for a modification request (e.g. multiple 80mm holes), you MUST list them and ASK the user if they want to change "All" or a specific one. NEVER proceed silently with just the first match.
   - **LIBRARIES**: NEVER use `pypycatia`. ONLY use `from pycatia import catia`.
   - **MODIFICATION**: To change a dimension (like "80mm"), favor modifying the **Parameter** in `part.parameters`. Loop through parameters and use `if "Radius.22\\Radius" in param.name:`.
   - **PARAMETER PATH**: Check `param.name` using the exact string provided (e.g., `Radius.22\\Radius`).
   - **FUZZY VALUE MATCHING**: NEVER use `==`. Always use `abs(val - target) < 0.1`.
   - **UPDATE**: Call `part.update()` and `doc.product.update()`. If it errors, log it but don't stop.
6. **Debugging & Execution (CRITICAL)**:
   - **NO SILENT FAILURES**: Do NOT use `try...except` to hide errors.
   - **LOG EVERYTHING**: Every major step MUST be printed.
   - **PROPERTIES**: For radius/diameter, use `.com_object.Radius.Value` (PascalCase).
7. Always wrap your python code in ```python blocks.
8. Provide a clear summary of your reasoning and what the script accomplished.
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
