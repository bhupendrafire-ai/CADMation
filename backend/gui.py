import sys
import os

# So pydantic/.env and logs resolve next to the EXE when bundled (PyInstaller).
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(os.path.abspath(sys.executable)))

import threading
import time
import logging
import urllib.request
import urllib.error
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, QCoreApplication
from PySide6.QtGui import QColor, QIcon
import uvicorn
from app.main import app

import faulthandler

import tempfile

# Enable faulthandler to a file to capture hard crashes (segfaults)
# Move log directory to LOCAL C: DRIVE to isolate from H: drive network lag
log_dir = os.path.join(tempfile.gettempdir(), "CADMation")
os.makedirs(log_dir, exist_ok=True)

crash_log_path = os.path.join(log_dir, "crash_trace.log")
faulthandler.enable(file=open(crash_log_path, "w", encoding="utf-8"))

# Redirection of stdout/stderr to avoid crashes in windowed mode (no console)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    # Instead of devnull, redirect stderr to a real file so we can see Python trackbacks
    sys.stderr = open(os.path.join(log_dir, "gui_stderr.log"), "w", encoding="utf-8")

# Force software rendering and disable GPU completely to avoid white screen on some hardware
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --no-sandbox --disable-software-rasterizer --disable-gpu-compositing --disable-gpu-rasterization --disable-gpu-sandbox"
os.environ["QT_OPENGL"] = "software"

# Configure logging to LOCAL C: DRIVE
log_path = os.path.join(log_dir, "gui_debug.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, mode='w', encoding="utf-8")
    ]
)
logger = logging.getLogger("CADMation-GUI")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CADMation Enterprise v2.3.0")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)
        
        # Set Window Icon
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # UI Styling (Dark Theme)
        self.setStyleSheet("background-color: #0d0d0e;")
        
        # Create WebEngineView
        self.browser = QWebEngineView()
        # Ensure page background matches window background
        self.browser.page().setBackgroundColor(QColor("#0d0d0e"))
        self.setCentralWidget(self.browser)
        
        # Connect signals for debugging
        self.browser.loadStarted.connect(lambda: logger.info("Browser: Load started..."))
        self.browser.loadFinished.connect(self._on_load_finished)
        
        # Load the backend URL
        url = "http://127.0.0.1:8000"
        logger.info(f"Main browser window loading {url}...")
        self.browser.load(QUrl(url))

    def _on_load_finished(self, success):
        if success:
            logger.info("Browser: Web page loaded successfully.")
        else:
            logger.error("Browser: Failed to load web page. Backend might be unreachable.")
            # Show a recovery message or try to reload once?
            # For now, just log.

    def closeEvent(self, event):
        logger.info("Main window close event triggered.")
        super().closeEvent(event)

def run_server():
    """Starts the FastAPI server in a background thread with recovery isolation."""
    try:
        logger.info(f"Starting FastAPI backend server (Logs: {log_dir})")
        # log_config=None is CRITICAL in frozen windowed apps to prevent 
        # uvicorn from checking sys.stdout.isatty() which crashes when stdout is None.
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info", log_config=None)
    except Exception as e:
        logger.critical(f"FATAL: Backend server thread failed: {e}", exc_info=True)

def wait_for_backend(timeout_s: float = 30.0) -> bool:
    deadline = time.time() + timeout_s
    url = "http://127.0.0.1:8000/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    return False

import subprocess

_backend_proc = None

def spawn_backend_worker():
    global _backend_proc
    logger.info("Watchdog: Spawning backend worker process...")
    cmd = [sys.executable, "--server-only"] if getattr(sys, "frozen", False) else [sys.executable, sys.argv[0], "--server-only"]
    
    creation_flags = 0
    if os.name == 'nt':
        creation_flags = subprocess.CREATE_NO_WINDOW

    stderr_file = open(os.path.join(log_dir, "gui_stderr.log"), "a", encoding="utf-8")
    
    _backend_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
        creationflags=creation_flags
    )
    logger.info(f"Watchdog: Backend spawned with PID {_backend_proc.pid}")

def watchdog_loop():
    global _backend_proc
    while True:
        time.sleep(2.0)
        if _backend_proc is not None:
            retcode = _backend_proc.poll()
            if retcode is not None:
                logger.error(f"Watchdog: Backend process crashed with code {retcode}! Respawning in 1s...")
                time.sleep(1.0)
                spawn_backend_worker()

def main():
    if "--server-only" in sys.argv:
        # We are the hidden background worker
        run_server()
        sys.exit(0)

    logger.info("="*60)
    logger.info("  CADMation Enterprise - Professional Engineering Suite")
    logger.info("="*60)

    # Set attributes before QApplication creation
    QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
    
    # 1. Start backend process via subprocess
    spawn_backend_worker()
    
    # 2. Start the Watchdog thread to monitor the subprocess
    watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
    watchdog_thread.start()

    # 3. Wait for backend to warm up
    logger.info("Waiting for backend to initialize...")
    if not wait_for_backend(timeout_s=35.0):
        logger.error("Backend did not become ready in time; the UI may fail to load.")

    # 4. Launch the native window (Qt)
    logger.info("Launching native GUI window...")
    qt_app = QApplication(sys.argv)
    qt_app.setStyle("Fusion")
    
    try:
        window = MainWindow()
        window.show()
        
        exit_code = qt_app.exec()
        
        # Kill backend when GUI closes
        if _backend_proc and _backend_proc.poll() is None:
            logger.info("Killing backend worker before exit...")
            _backend_proc.terminate()
            
        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"FATAL: Application crashed in main thread: {e}", exc_info=True)
        if _backend_proc and _backend_proc.poll() is None:
            _backend_proc.terminate()
        sys.exit(1)

if __name__ == "__main__":
    main()
