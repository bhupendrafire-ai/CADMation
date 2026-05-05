import logging
import requests
from typing import Dict, Optional, List
from app.services.license_manager import TOOLROOM_API_URL, license_manager

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        # We store the session in memory. It will be cleared when the app closes,
        # forcing the user to log in again on the next launch (No "Remember Me").
        self.current_user_token: Optional[str] = None
        self.current_user: Optional[Dict] = None

    def login(self, email: str, password: str) -> Dict:
        """Proxies login credentials to ToolRoom ERP to retrieve a session token."""
        try:
            url = f"{TOOLROOM_API_URL}/api/cadmation/auth/login"
            response = requests.post(url, json={
                "email": email,
                "password": password,
                "machineId": license_manager.machine_id
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("token"):
                    self.current_user_token = data["token"]
                    self.current_user = data["user"] # This now contains id, name, etc.
                    logger.info(f"User {email} logged in successfully (ID: {self.current_user.get('id')}).")
                    return {"success": True, "user": self.current_user}
                else:
                    return {"success": False, "message": "Invalid response from server."}
            else:
                try:
                    data = response.json()
                    return {"success": False, "message": data.get("error", "Authentication failed.")}
                except:
                    return {"success": False, "message": f"Authentication failed with status {response.status_code}."}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Login network error: {e}")
            return {"success": False, "message": "Could not connect to the authentication server."}

    def logout(self):
        """Clears the current in-memory user session."""
        self.current_user_token = None
        self.current_user = None
        logger.info("User logged out.")

    def get_assigned_projects(self) -> List[Dict]:
        """Fetches the assigned projects from ToolRoom using the active user token."""
        if not self.current_user_token:
            return []

        try:
            url = f"{TOOLROOM_API_URL}/api/cadmation/projects"
            headers = {"Authorization": f"Bearer {self.current_user_token}"}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("projects", [])
            else:
                logger.warning(f"Failed to fetch projects, status: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching projects: {e}")
            return []

auth_service = AuthService()
