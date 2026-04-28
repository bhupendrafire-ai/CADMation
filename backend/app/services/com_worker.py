import threading
import queue
import logging
import pythoncom
import time
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)

class COMSentinel:
    """
    A dedicated, permanent worker thread for all CATIA COM operations.
    Ensures absolute Physical Thread Affinity, satisfying COM STA requirements.
    """
    def __init__(self):
        self._task_queue = queue.Queue()
        self._thread = None
        self._running = False
        self._thread_id = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop, 
            name="COM-SENTINEL", 
            daemon=True
        )
        self._thread.start()
        logger.info("COM Sentinel: Dedicated worker thread started.")

    def stop(self):
        self._running = False
        self._task_queue.put(None) # Poison pill
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("COM Sentinel: Worker thread stopped.")

    def _worker_loop(self):
        """Persistent loop running on the SAME physical thread for the life of the app."""
        self._thread_id = threading.get_ident()
        logger.info(f"COM-SENTINEL: Initializing STA on physical thread {self._thread_id}")
        
        # 1. Initialize COM once and for all on this thread
        pythoncom.CoInitialize()
        
        try:
            while self._running:
                task = self._task_queue.get()
                if task is None: # Exit signal
                    break
                
                func, args, kwargs, result_event, result_box = task
                
                try:
                    # Execute the function in the STABLE environment
                    res = func(*args, **kwargs)
                    result_box["data"] = res
                    result_box["success"] = True
                except Exception as e:
                    logger.error(f"COM-SENTINEL: Task failed: {e}")
                    result_box["error"] = str(e)
                    result_box["success"] = False
                finally:
                    result_event.set()
                    self._task_queue.task_done()
        finally:
            logger.info("COM-SENTINEL: Cleaning up STA.")
            pythoncom.CoUninitialize()

    def run(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executes a function on the dedicated COM Sentinel thread and blocks for result.
        Safe to call from any AnyIO/asyncio background thread.
        """
        if not self._running:
            self.start()

        result_event = threading.Event()
        result_box = {"data": None, "success": False, "error": None}
        
        task = (func, args, kwargs, result_event, result_box)
        self._task_queue.put(task)
        
        # Wait for the worker to finish
        # We use a 120s timeout to prevent thread hangs during crash scenarios
        if not result_event.wait(timeout=120):
            raise TimeoutError("COM Sentinel: Task timed out (CATIA unresponsive?)")
            
        if not result_box["success"]:
            raise Exception(result_box["error"] or "Unknown worker error")
            
        return result_box["data"]

# Singleton instance
com_sentinel = COMSentinel()
