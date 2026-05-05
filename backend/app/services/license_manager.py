import os
import sys
import json
import uuid
import platform
import logging
import requests
import base64
import hmac
import hashlib
from typing import Optional, Dict
from app.config import settings

logger = logging.getLogger(__name__)

# Configurable ToolRoom URL
TOOLROOM_API_URL = settings.toolroom_api_url
# Wait, for safety, since we don't know the exact production URL, I will make it easily configurable.
# Actually, I'll default to localhost:3000 for local dev unless specified.
# Let's use an env var with a fallback.
if "toolroom" not in TOOLROOM_API_URL.lower() and "localhost" not in TOOLROOM_API_URL:
    TOOLROOM_API_URL = "http://localhost:3000"

def get_appdata_dir() -> str:
    """Returns the path to the CADMation AppData directory where the license will be stored."""
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    
    config_dir = os.path.join(appdata, "CADMation")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

LICENSE_FILE_PATH = os.path.join(get_appdata_dir(), "license.dat")

class LicenseManager:
    def __init__(self):
        self.machine_id = self._generate_machine_id()
        self.current_token: Optional[str] = None
        self._load_token()

    def _generate_machine_id(self) -> str:
        """Generates a stable hardware ID based on MAC address and node info."""
        mac_num = uuid.getnode()
        system_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}-{mac_num}"
        # Hash it to ensure a clean, fixed-length alphanumeric string
        return hashlib.sha256(system_info.encode()).hexdigest()[:16].upper()

    def _load_token(self):
        """Loads the license token from disk if it exists."""
        if os.path.exists(LICENSE_FILE_PATH):
            try:
                with open(LICENSE_FILE_PATH, "r") as f:
                    data = json.load(f)
                    self.current_token = data.get("token")
            except Exception as e:
                logger.error(f"Failed to load license file: {e}")
                self.current_token = None

    def _save_token(self, token: str):
        """Saves the license token to disk."""
        try:
            with open(LICENSE_FILE_PATH, "w") as f:
                json.dump({"token": token}, f)
            self.current_token = token
            logger.info("License token saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save license file: {e}")

    def get_license_status(self) -> Dict:
        """Returns the current licensing status for the UI."""
        return {
            "is_activated": self.current_token is not None,
            "machine_id": self.machine_id
        }

    def activate_online(self, license_key: str) -> Dict:
        """Attempts to activate the software against the ToolRoom Licensing Server."""
        try:
            url = f"{TOOLROOM_API_URL}/api/cadmation/activate"
            logger.info(f"Attempting activation at {url} with Machine ID: {self.machine_id}")
            
            response = requests.post(url, json={
                "licenseKey": license_key.strip(),
                "machineId": self.machine_id
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("token"):
                    self._save_token(data["token"])
                    return {"success": True, "message": "Activation successful."}
                else:
                    return {"success": False, "message": data.get("error", "Unknown error from server.")}
            elif response.status_code == 403:
                data = response.json()
                return {"success": False, "message": data.get("error", "Activation denied.")}
            else:
                return {"success": False, "message": f"Server error: {response.status_code}"}

        except requests.exceptions.RequestException as e:
            logger.error(f"Activation network error: {e}")
            return {"success": False, "message": "Could not connect to the licensing server. Please check your internet connection."}
        except Exception as e:
            logger.error(f"Unexpected activation error: {e}")
            return {"success": False, "message": "An unexpected error occurred during activation."}

    def revoke_local_license(self):
        """Deletes the local activation token, forcing a reactivation."""
        self.current_token = None
        if os.path.exists(LICENSE_FILE_PATH):
            try:
                os.remove(LICENSE_FILE_PATH)
                logger.info("Local license token has been revoked/deleted.")
            except Exception as e:
                logger.error(f"Failed to delete license file: {e}")

license_manager = LicenseManager()
