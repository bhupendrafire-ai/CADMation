"""
CADMation — FastAPI entry point.

Sets up CORS, mounts API routers, and exposes a health check endpoint.
The server runs locally alongside an active CATIA V5 session.
"""

import logging
import os

# Configure logging to write to a file for persistent debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("cadmation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import catia, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks. Currently a placeholder for future COM init."""
    yield


app = FastAPI(
    title="CADMation",
    version="0.1.0",
    description="Local AI copilot for CATIA V5 sheet metal design",
    lifespan=lifespan,
)

# --- CORS (allow the Vite dev server) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# --- Routers ---
app.include_router(catia.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# --- Frontend Serving (Final Step Logic) ---
import sys
# Path to the built frontend
base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
FRONTEND_DIST = os.path.join(base_path, "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Exclude /api routes from being caught by the static fallback
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        static_file = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(static_file):
            return FileResponse(static_file)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


from app.services.catia_bridge import catia_bridge

# ... existing app and router definitions ...

@app.get("/api/health")
async def health():
    """Quick liveness check. Including real CATIA status."""
    return {
        "status": "ok",
        "catia": catia_bridge.check_connection()
    }


if __name__ == "__main__":
    import uvicorn
    import sys
    try:
        print("\n" + "="*60)
        print("  CADMation AI Copilot for CATIA V5 - Standalone Server")
        print("="*60)
        print(f"  * Mode:        {'Standalone' if getattr(sys, 'frozen', False) else 'Development'}")
        print("  * Access UI:   http://localhost:8000")
        print("="*60 + "\n")
        
        # Check for .env file location
        env_path = os.path.join(os.getcwd(), ".env")
        if not os.path.exists(env_path):
             print(f"  [!] Note: No .env file found at: {os.getcwd()}")
             print("      If your AI keys are not in system environment variables,")
             print("      please create a .env file next to this EXE.\n")

        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

    except Exception as e:
        print(f"\n[FATAL ERROR] Failed to start server: {e}")
        input("\nPress Enter to close this window...")
