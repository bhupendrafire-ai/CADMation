import os
import json
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

HISTORY_DIR = "chat_history"

class HistoryService:
    def __init__(self):
        # Store in project root or app data? Project root for now as requested.
        self.history_dir = os.path.join(os.getcwd(), HISTORY_DIR)
        os.makedirs(self.history_dir, exist_ok=True)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lists all chat sessions found in the history directory."""
        sessions = []
        try:
            for filename in os.listdir(self.history_dir):
                if filename.endswith(".json"):
                    path = os.path.join(self.history_dir, filename)
                    with open(path, "r") as f:
                        data = json.load(f)
                        sessions.append({
                            "id": data.get("id"),
                            "name": data.get("name", "Untitled Chat"),
                            "updated_at": data.get("updated_at"),
                            "last_doc": data.get("last_doc")
                        })
            # Sort by updated_at descending
            sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        except Exception as e:
            logger.error(f"HistoryService: Failed to list sessions: {e}")
        return sessions

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific chat session by ID."""
        path = os.path.join(self.history_dir, f"{session_id}.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"HistoryService: Failed to load session {session_id}: {e}")
        return None

    def save_session(self, session_id: str, messages: List[Dict[str, Any]], name: Optional[str] = None, last_doc: Optional[str] = None, user_id: Optional[str] = None, user_name: Optional[str] = None):
        """Saves messages to a session file, updating metadata."""
        path = os.path.join(self.history_dir, f"{session_id}.json")
        
        # Load existing data to preserve the FIRST name set
        old_data = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    old_data = json.load(f)
            except: pass

        # Determine name:
        # 1. If explicit name provided, use it
        # 2. Else if old name exists and is not default, keep it (Requirement: First Doc Name sticks)
        # 3. Else if last_doc provided, use it as the first name
        # 4. Otherwise default
        existing_name = old_data.get("name")
        if name:
            session_name = name
        elif existing_name and existing_name != "New Conversation":
            session_name = existing_name
        elif last_doc:
            session_name = last_doc
        else:
            session_name = "New Conversation"

        data = {
            "id": session_id,
            "name": session_name,
            "last_doc": last_doc or old_data.get("last_doc"),
            "user_id": user_id or old_data.get("user_id"),
            "user_name": user_name or old_data.get("user_name"),
            "updated_at": datetime.now().isoformat(),
            "messages": messages
        }

        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"HistoryService: Saved session {session_id}")
        except Exception as e:
            logger.error(f"HistoryService: Failed to save session {session_id}: {e}")

    def create_session(self) -> str:
        """Creates a new unique session ID."""
        return str(uuid.uuid4())

    def list_final_sessions(self) -> List[Dict[str, Any]]:
        """Lists sessions that have reached the Final Document stage (BOM editor present)."""
        sessions = []
        try:
            for filename in os.listdir(self.history_dir):
                if filename.endswith(".json"):
                    path = os.path.join(self.history_dir, filename)
                    with open(path, "r") as f:
                        data = json.load(f)
                        # Check if any message contains bomEditor data
                        has_bom = any(msg.get("bomEditor") for msg in data.get("messages", []))
                        if has_bom:
                            sessions.append({
                                "id": data.get("id"),
                                "name": data.get("name", "Final BOM"),
                                "updated_at": data.get("updated_at"),
                                "last_doc": data.get("last_doc"),
                                "user_name": data.get("user_name")
                            })
            sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        except Exception as e:
            logger.error(f"HistoryService: Failed to list final sessions: {e}")
        return sessions

# Singleton
history_service = HistoryService()
