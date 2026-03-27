# region agent log
import json
import os
import sys
import time

_SESSION = "66053b"
_LOG_PATH = None


def _workspace_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _debug_logs_dir() -> str:
    d = os.path.join(_workspace_root(), "debug_logs")
    os.makedirs(d, exist_ok=True)
    return d


def start_new_bom_debug_log() -> str:
    """New file per BOM WebSocket run; previous files are never overwritten."""
    global _LOG_PATH
    d = _debug_logs_dir()
    ts = time.strftime("%Y%m%d_%H%M%S")
    ms = int(time.time() * 1000) % 10000
    fn = f"debug-{_SESSION}_{ts}_{ms:04d}_{os.getpid()}.log"
    _LOG_PATH = os.path.join(d, fn)
    rec = {
        "sessionId": _SESSION,
        "hypothesisId": "RUN",
        "location": "debug_agent_log.start_new_bom_debug_log",
        "message": "bom_debug_log_started",
        "data": {"path": _LOG_PATH},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass
    return _LOG_PATH


def current_debug_log_path():
    return _LOG_PATH


def agent_ndjson(hypothesis_id: str, location: str, message: str, data=None) -> None:
    global _LOG_PATH
    try:
        if _LOG_PATH is None:
            start_new_bom_debug_log()
        rec = {
            "sessionId": _SESSION,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass


# endregion
