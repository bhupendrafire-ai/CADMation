import threading
import time
import logging
import requests
import queue
import base64
import os
import json
from datetime import datetime
from typing import List, Dict

from app.services.license_manager import license_manager, TOOLROOM_API_URL
import __main__

logger = logging.getLogger(__name__)

class TelemetryWorker:
    def __init__(self):
        self.event_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.is_running = False
        self.sync_interval = 60 * 5  # Sync every 5 minutes if online
        from app.services.license_manager import get_appdata_dir
        self.cache_path = os.path.join(get_appdata_dir(), "telemetry_cache.json")

    def start(self):
        """Starts the background telemetry thread."""
        if not self.is_running:
            self.is_running = True
            self._load_offline_events()
            self.worker_thread.start()
            self.log_event("STARTUP", {"version": getattr(__main__, "__version__", "unknown")})
            logger.info("Telemetry worker started.")

    def _load_offline_events(self):
        """Loads events cached on disk into the queue."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r") as f:
                    events = json.load(f)
                    for event in events:
                        self.event_queue.put(event)
                logger.info(f"Loaded {len(events)} offline events from cache.")
            except Exception as e:
                logger.error(f"Failed to load telemetry cache: {e}")

    def _save_offline_events(self):
        """Saves current queue items to disk for persistence."""
        # Note: This is a bit tricky with queue.Queue since we can't iterate without destructive reading
        # We'll read everything, save it, and put it back.
        events = []
        while not self.event_queue.empty():
            try:
                events.append(self.event_queue.get_nowait())
            except: break
        
        if events:
            try:
                with open(self.cache_path, "w") as f:
                    json.dump(events, f)
                # Put them back in the queue
                for e in events:
                    self.event_queue.put(e)
            except Exception as e:
                logger.error(f"Failed to save telemetry cache: {e}")

    def _clear_offline_cache(self):
        """Deletes the cache file after successful sync."""
        if os.path.exists(self.cache_path):
            try:
                os.remove(self.cache_path)
            except: pass

    def stop(self):
        """Signals the worker to stop."""
        self.is_running = False
        # Push a dummy event to wake up the queue if it's blocking
        self.event_queue.put(None)

    def log_event(self, event_type: str, details: Dict = None):
        """Pushes an event to the queue to be synced later."""
        if not license_manager.current_token:
            return  # Don't log if not activated

        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "eventType": event_type,
            "details": details or {},
            "appVersion": getattr(__main__, "__version__", "unknown")
        }
        
        # Extract bomMetadata if present in details
        if details and "bomMetadata" in details:
            event["bomMetadata"] = details["bomMetadata"]
            # Clean up details to avoid duplication if desired, 
            # though keeping it doesn't hurt much.
            
        self.event_queue.put(event)

    def _run_loop(self):
        """Main background loop."""
        last_sync_time = time.time()
        
        while self.is_running:
            try:
                # Wait for an event, or timeout to do a periodic heartbeat
                timeout = max(1.0, self.sync_interval - (time.time() - last_sync_time))
                try:
                    event = self.event_queue.get(timeout=timeout)
                    if event is None:
                        continue # Wake up call or shutdown
                except queue.Empty:
                    # Timeout reached, time for a heartbeat
                    event = None

                # Collect all available events from the queue
                events_to_sync = []
                if event:
                    events_to_sync.append(event)
                
                while not self.event_queue.empty():
                    try:
                        e = self.event_queue.get_nowait()
                        if e: events_to_sync.append(e)
                    except queue.Empty:
                        break

                # If no events, create a heartbeat
                if not events_to_sync and (time.time() - last_sync_time) >= self.sync_interval:
                    events_to_sync.append({
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "eventType": "HEARTBEAT",
                        "details": {},
                        "appVersion": getattr(__main__, "__version__", "unknown")
                    })

                if events_to_sync and license_manager.current_token:
                    # Parse the token to get the licenseId
                    # The token is base64(payload:signature) and payload is licenseId:machineId:timestamp
                    try:
                        decoded = base64.b64decode(license_manager.current_token).decode('utf-8')
                        payload = decoded.split(':')[0:3]
                        license_id = payload[0]
                        
                        # Sync with server
                        success = self._sync_with_server(license_id, events_to_sync)
                        if success:
                            last_sync_time = time.time()
                            self._clear_offline_cache()
                        else:
                            # Re-queue events if sync failed (network down)
                            for e in events_to_sync:
                                if e["eventType"] != "HEARTBEAT": # Don't requeue heartbeats
                                    self.event_queue.put(e)
                            self._save_offline_events()
                    except Exception as parse_error:
                        logger.error(f"Failed to parse local token for telemetry: {parse_error}")

            except Exception as e:
                logger.error(f"Telemetry worker encountered an error: {e}")
                time.sleep(10) # Backoff on crash

    def _sync_with_server(self, license_id: str, events: List[Dict]) -> bool:
        """Attempts to push events to the ToolRoom server and checks license status."""
        try:
            url = f"{TOOLROOM_API_URL}/api/cadmation/telemetry"
            response = requests.post(url, json={
                "licenseId": license_id,
                "machineId": license_manager.machine_id,
                "events": events
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "REVOKED":
                    logger.warning("TELEMETRY: Server reported license as REVOKED! Locking application.")
                    license_manager.revoke_local_license()
                return True
            else:
                logger.debug(f"Telemetry sync failed with status {response.status_code}")
                return False

        except requests.exceptions.RequestException:
            # Expected if offline. We fail gracefully.
            return False

# Singleton instance
telemetry_worker = TelemetryWorker()
