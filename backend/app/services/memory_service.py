import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

MEMORY_FILE = "design_memory.json"

class MemoryService:
    def __init__(self):
        self.memory_path = os.path.join(os.getcwd(), MEMORY_FILE)
        self.data = self._load_memory()

    def _load_memory(self) -> Dict[str, Any]:
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"MemoryService: Failed to load memory: {e}")
        return {"verified_patterns": [], "rejected_patterns": [], "user_rules": []}

    def _save_memory(self):
        try:
            with open(self.memory_path, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"MemoryService: Failed to save memory: {e}")

    def save_success(self, prompt: str, code: str):
        """Stores a verified successful script pattern."""
        self.data["verified_patterns"].append({
            "prompt": prompt,
            "code": code,
            "timestamp": "now" # Simple placeholder
        })
        self._save_memory()
        logger.info(f"MemoryService: Saved verified pattern for: {prompt[:30]}...")

    def log_failure(self, prompt: str, code: str, feedback: str):
        """Stores a failed pattern to avoid repeating it."""
        self.data["rejected_patterns"].append({
            "prompt": prompt,
            "code": code,
            "feedback": feedback
        })
        self._save_memory()

    def add_user_rule(self, rule: str):
        """Adds a permanent design rule learned from user feedback."""
        if rule not in self.data["user_rules"]:
            self.data["user_rules"].append(rule)
            self._save_memory()

    def get_context_for_prompt(self) -> str:
        """Returns a string summary of memory to inject into the LLM prompt."""
        rules = "\n".join([f"- {r}" for r in self.data["user_rules"]])
        patterns = ""
        for p in self.data["verified_patterns"][-3:]: # Only take last 3 for brevity
            patterns += f"Task: {p['prompt']}\nVerified Method: {p['code']}\n\n"
        
        context = ""
        if rules:
            context += f"USER-DEFINED DESIGN RULES:\n{rules}\n\n"
        if patterns:
            context += f"PREVIOUSLY VERIFIED SUCCESSFUL PATTERNS:\n{patterns}\n"
        
        return context

# Singleton
memory_service = MemoryService()
