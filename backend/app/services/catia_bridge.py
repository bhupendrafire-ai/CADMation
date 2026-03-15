import logging
import win32com.client
import pythoncom
import threading

logger = logging.getLogger(__name__)

class CATIABridge:
    _instance = None
    # We remove the cached _caia to avoid inter-thread apartment issues
    # Instead, we'll re-connect or use thread-local storage if performance is an issue

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CATIABridge, cls).__new__(cls)
        return cls._instance

    def _ensure_com_init(self):
        """Ensures COM is initialized for the current thread."""
        try:
            # CoInitialize identifies the current thread as part of an STA
            pythoncom.CoInitialize()
        except Exception:
            pass

    def get_application(self):
        """
        Attempts to connect to a running CATIA V5 session.
        Respects thread apartments by re-acquiring the object.
        """
        self._ensure_com_init()
        
        try:
            # Re-acquire the proxy in the current thread's apartment
            # This is safer than sharing a cached object across threads
            dispatch = win32com.client.GetActiveObject("CATIA.Application")
            
            # Verify the connection is responsive
            _ = dispatch.Name 
            logger.info("Successfully acquired CATIA connection in current thread.")
            return dispatch
        except Exception as e:
            # Log the error for debugging, even if we return None
            # Only log if it's not a standard 'Operation unavailable' error to avoid spam
            if "Operation unavailable" not in str(e):
                logger.debug(f"CATIA connection attempt failed: {e}")
            return None

    def get_active_document_name(self) -> str | None:
        """Returns the display name of the active document (window caption)."""
        caa = self.get_application()
        if not caa:
            return None
        
        try:
            # Prefer Window Caption as it shows the true filename for imports (e.g. .stp)
            try:
                caption = caa.ActiveWindow.Caption
                if caption: return caption
            except: pass
            
            return caa.ActiveDocument.Name
        except Exception:
            return "No Active Document"

    def check_connection(self) -> bool:
        """Liveness check for the COM connection."""
        return self.get_application() is not None

# Singleton accessor
catia_bridge = CATIABridge()
