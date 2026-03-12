"""
catia_bridge.py — COM wrapper for pycatia connections.

Provides a singleton-style accessor to the running CATIA V5 application
object. Handles connection lifecycle: connect, reconnect, and graceful
failure when CATIA is not running.
"""

import logging
from pycatia import catia
# from pycatia.exception_handling import CATIAApplicationException # Not strictly needed for logic fix

logger = logging.getLogger(__name__)

class CATIABridge:
    _instance = None
    _caia = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CATIABridge, cls).__new__(cls)
        return cls._instance

    def get_application(self):
        """
        Attempts to connect to a running CATIA V5 session.
        Returns the catia application object or None if not found.
        """
        try:
            # Note: pycatia.catia() connects to the active session
            if self._caia is None:
                self._caia = catia()
            
            # Simple check to see if the session is still responsive
            _ = self._caia.name 
            return self._caia
        except Exception as e:
            logger.warning(f"Failed to connect to CATIA V5: {e}")
            self._caia = None
            return None

    def get_active_document_name(self) -> str | None:
        """Returns the name of the active document or None."""
        caa = self.get_application()
        if not caa:
            return None
        
        try:
            return caa.active_document.name
        except Exception:
            return "No Active Document"

    def check_connection(self) -> bool:
        """Liveness check for the COM connection."""
        return self.get_application() is not None

# Singleton accessor
catia_bridge = CATIABridge()
