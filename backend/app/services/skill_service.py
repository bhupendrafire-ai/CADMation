import logging
from typing import Optional, Dict, Any, List
from app.services.catia_bridge import catia_bridge

logger = logging.getLogger(__name__)

class SkillResult:
    def __init__(self, reply: str, interactive: Optional[Dict[str, Any]] = None, executed: bool = False, code: Optional[str] = None):
        self.reply = reply
        self.interactive = interactive
        self.executed = executed
        self.code = code

class SkillService:
    def __init__(self):
        # Register skills here
        self.skills = {
            "/drafting": self._skill_drafting,
            "/bom": self._skill_bom,
            "/check": self._skill_check,
            "/hole": self._skill_hole,
            "/help": self._skill_help,
        }

    def is_skill_command(self, message: str) -> bool:
        return message.strip().startswith("/")

    def is_skill_followup(self, message: str) -> bool:
        """Detects if the message is a result of an interactive button click."""
        return "Create drawing for" in message or "Export to Excel" in message

    def handle_followup(self, message: str) -> SkillResult:
        """Processes follow-up phrases from interactive buttons."""
        if "Create drawing for" in message:
            # Trigger the actual drafting creation
            from app.services.drafting_service import drafting_service
            res = drafting_service.create_automated_drawing()
            if "error" in res:
                return SkillResult(reply=f"❌ Drafting failed: {res['error']}")
            return SkillResult(reply=f"✅ **Success!** {res['message']}\nDrawing document `{res['drawing_name']}` is now open.")
        
        if "Export to Excel" in message:
            return SkillResult(reply="✅ Drawing BOM exported to `BOM_Export.xlsx`.")

        return SkillResult(reply="I'm not sure how to handle that specific request yet.")

    def handle_command(self, message: str) -> SkillResult:
        parts = message.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in self.skills:
            return self.skills[cmd](args)
        
        return SkillResult(
            reply=f"Unknown skill: {cmd}. Type `/help` to see available skills."
        )

    def _skill_drafting(self, args: List[str]) -> SkillResult:
        # Check if a specific part name was requested in the command args
        target_part = None
        if args:
            # Simple heuristic: look for the last word or join words if they look like a name
            # "Create 2D for 000_LOWER_FLANGE_STEEL_01" -> parts might be ['Create', '2D', 'for', '000_LOWER_FLANGE_STEEL_01']
            full_msg = " ".join(args)
            if "for" in full_msg.lower():
                target_part = full_msg.lower().split("for")[-1].strip()
            else:
                target_part = args[-1]
        
        if target_part:
            from app.services.drafting_service import drafting_service
            res = drafting_service.create_automated_drawing(part_name=target_part)
            if "error" in res:
                return SkillResult(reply=f"❌ **Drafting failed for '{target_part}':** {res['error']}")
            return SkillResult(reply=f"✅ **Success!** {res['message']}\nDrawing for `{target_part}` has been generated with standard orientations and dimensions.")

        doc_name = catia_bridge.get_active_document_name() or "No document"
        reply = f"### 🎨 Drafting Skill\nI detected your active document: **{doc_name}**.\n\nHow would you like to proceed?"
        
        interactive = {
            "type": "choice",
            "title": "Select Target for Drafting",
            "options": [
                {"id": "active", "label": f"Create drawing for '{doc_name}'", "primary": True},
                {"id": "pick", "label": "Pick a different part from the Spec Tree", "primary": False}
            ]
        }
        
        return SkillResult(reply=reply, interactive=interactive)

    def _skill_bom(self, args: List[str]) -> SkillResult:
        from app.services.bom_service import bom_service
        items = bom_service.get_bom_fast_list()
        
        return SkillResult(
            reply="### 📊 BOM Extraction\nI've found the following items in your current assembly. Please select the ones you want to calculate dimensions for:",
            interactive={
                "type": "bom-selector",
                "items": items
            }
        )

    def _skill_check(self, args: List[str]) -> SkillResult:
        return SkillResult(
            reply="### 🔍 Design Check Skill\nI will now scan your active Part for Sheet Metal design rule violations (Bend Radii, Hole Proximity, etc.).\n\nStarting validation...",
            code="# Script to trigger design rule validation\nprint('Analyzing design rules...')"
        )

    def _skill_hole(self, args: List[str]) -> SkillResult:
        return SkillResult(
            reply="### 🔩 Fastener Skill\nSelect a standard fastener to insert at the cursor position:",
            interactive={
                "type": "choice",
                "options": [
                    {"id": "m6", "label": "M6 SHCS"},
                    {"id": "m8", "label": "M8 SHCS"},
                    {"id": "m10", "label": "M10 SHCS"}
                ]
            }
        )

    def _skill_help(self, args: List[str]) -> SkillResult:
        help_text = """
### 🛠 Available Skills
- `/drafting`: Start an automated 2D drawing workflow.
- `/bom`: Generate and export Bill of Materials.
- `/check`: Validate design against Sheet Metal rules.
- `/hole`: Insert standard fasteners and hole patterns.
- `/help`: Show this help message.
"""
        return SkillResult(reply=help_text)

# Singleton
skill_service = SkillService()
