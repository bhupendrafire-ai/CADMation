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

    def save_session(self, session_id: str, messages: List[Dict[str, Any]], last_doc: Optional[str] = None):
        """Saves messages to a session file, updating metadata."""
        path = os.path.join(self.history_dir, f"{session_id}.json")
        
        # Determine name: Use last_doc if provided, otherwise keep existing or default
        name = last_doc if last_doc else "New Conversation"
        
        # If we already have a session, preserve its name unless a better one (doc name) is provided
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    old_data = json.load(f)
                    if not last_doc:
                        name = old_data.get("name", name)
            except: pass

        data = {
            "id": session_id,
            "name": name,
            "last_doc": last_doc or (old_data.get("last_doc") if 'old_data' in locals() else None),
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

# Singleton
history_service = HistoryService()
