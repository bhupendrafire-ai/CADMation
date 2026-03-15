import sys
import os
import threading
import time
import logging
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, QCoreApplication
from PySide6.QtGui import QColor
import uvicorn
from app.main import app

# Force software rendering and disable GPU completely to avoid white screen on some hardware
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --no-sandbox --disable-software-rasterizer --disable-gpu-compositing --disable-gpu-rasterization --disable-gpu-sandbox"
os.environ["QT_OPENGL"] = "software"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("gui_debug.log", mode='w')
    ]
)
logger = logging.getLogger("CADMation-GUI")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CADMation Copilot")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)
        
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
        url = "http://localhost:8000"
        logger.info(f"Main browser window loading {url}...")
        self.browser.load(QUrl(url))

    def _on_load_finished(self, success):
        if success:
            logger.info("Browser: Web page loaded successfully.")
        else:
            logger.error("Browser: Failed to load web page. Check if the backend is running.")

def run_server():
    """Starts the FastAPI server in a background thread."""
    logger.info("Starting FastAPI backend server...")
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"Backend server failed: {e}")

def main():
    logger.info("="*60)
    logger.info("  CADMation AI Copilot - Native GUI (Safe Graphics Mode)")
    logger.info("="*60)

    # Set attributes before QApplication creation
    QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
    
    # 1. Start backend thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 2. Give server a moment to warm up
    logger.info("Waiting for backend to initialize (10s)...")
    time.sleep(10) 

    # 3. Launch the native window (Qt)
    logger.info("Launching native GUI window...")
    qt_app = QApplication(sys.argv)
    qt_app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    exit_code = qt_app.exec()
    logger.info(f"Application exited with code {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
