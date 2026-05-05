"""
CADMation — FastAPI entry point.

Sets up CORS, mounts API routers, and exposes a health check endpoint.
The server runs locally alongside an active CATIA V5 session.
"""

import logging
import os

# Configure logging to write to a file in a writable location
import sys
if getattr(sys, 'frozen', False):
    # If running as EXE, log to the application folder or temp
    log_dir = os.path.dirname(sys.executable)
else:
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.abspath(os.path.join(log_dir, ".."))

log_file = os.path.join(log_dir, "cadmation.log")

try:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
except Exception as e:
    # Fallback to stream only if file fails
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
    print(f"Logging to file failed: {e}")

logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.catia import router as catia_router
from app.routers.chat import router as chat_router


from app.services.com_worker import com_sentinel
from app.services.telemetry_worker import telemetry_worker
from app.services.license_manager import license_manager
from pydantic import BaseModel

class ActivationRequest(BaseModel):
    license_key: str

class LoginRequest(BaseModel):
    email: str
    password: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting CADMation backend services...")
    com_sentinel.start()
    telemetry_worker.start()
    yield
    # Shutdown
    logger.info("Stopping CADMation backend services...")
    com_sentinel.stop()
    telemetry_worker.stop()


__version__ = "3.6.7"

app = FastAPI(
    title="CADMation Enterprise",
    version=__version__,
    description="Professional Enterprise AI copilot for CATIA V5 sheet metal design",
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
app.include_router(catia_router, prefix="/api")
app.include_router(chat_router, prefix="/api")

if getattr(sys, 'frozen', False):
    FRONTEND_DIST = os.path.join(sys._MEIPASS, "frontend", "dist")
else:
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    FRONTEND_DIST = os.path.join(base_path, "frontend", "dist")

@app.get("/api/health")
async def health():
    """Quick liveness check. Including real CATIA status."""
    return {
        "status": "ok",
        "catia": catia_bridge.check_connection()
    }

@app.get("/api/license/status")
async def get_license_status():
    return license_manager.get_license_status()

@app.post("/api/license/activate")
async def activate_license(req: ActivationRequest):
    return license_manager.activate_online(req.license_key)

from app.services.auth_service import auth_service

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    result = auth_service.login(req.email, req.password)
    if result["success"]:
        return result
    raise HTTPException(status_code=401, detail=result["message"])

@app.post("/api/auth/logout")
async def logout():
    auth_service.logout()
    return {"success": True}

@app.get("/api/auth/user")
async def get_current_user():
    return {
        "is_logged_in": auth_service.current_user is not None,
        "user": auth_service.current_user
    }

    if not auth_service.current_user:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"projects": auth_service.get_assigned_projects()}

from app.services.bom_service import bom_service
from typing import Any, Dict, List

class ReviewSubmissionRequest(BaseModel):
    items: List[Dict[str, Any]]
    projectId: str
    toolId: str
    projectName: str
    comment: str = ""

@app.post("/api/bom/submit-review")
async def submit_bom_for_review(req: ReviewSubmissionRequest):
    if not auth_service.current_user:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    metadata = {
        "projectId": req.projectId,
        "toolId": req.toolId,
        "projectName": req.projectName,
        "comment": req.comment
    }
    
    result = bom_service.submit_for_review(req.items, metadata)
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("message", "Submission failed"))

@app.get("/api/bom/reviews")
async def get_bom_reviews():
    """Proxies to ToolRoom ERP to get submitted reviews for the current user."""
    if not auth_service.current_user_token:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    try:
        from app.services.license_manager import TOOLROOM_API_URL
        import requests
        url = f"{TOOLROOM_API_URL}/api/cadmation/bom/reviews"
        headers = {"Authorization": f"Bearer {auth_service.current_user_token}"}
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch reviews from ToolRoom: {e}")
        return {"success": False, "reviews": []}

@app.get("/api/stats/leaderboard")
async def get_leaderboard():
    """Proxies to ToolRoom ERP to get the global scan leaderboard."""
    try:
        from app.services.license_manager import TOOLROOM_API_URL
        import requests
        url = f"{TOOLROOM_API_URL}/api/cadmation/stats/leaderboard"
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch leaderboard from ToolRoom: {e}")
        return {"success": False, "leaderboard": []}

@app.post("/api/stats/scan-increment")
async def increment_scan_count():
    """Notifies ToolRoom ERP that a scan has occurred for gamification."""
    if not auth_service.current_user_token:
        return {"success": False}
    
    try:
        from app.services.license_manager import TOOLROOM_API_URL
        import requests
        url = f"{TOOLROOM_API_URL}/api/cadmation/stats/scan-increment"
        headers = {"Authorization": f"Bearer {auth_service.current_user_token}"}
        requests.post(url, headers=headers, timeout=5)
        return {"success": True}
    except:
        return {"success": False}


if os.path.exists(FRONTEND_DIST):
    # Mount the /assets directory only if it exists, to prevent startup crashes
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    else:
        logger.warning(f"Frontend assets directory not found at {assets_dir}")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Exclude /api routes from being caught by the static fallback
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        static_file = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(static_file):
            return FileResponse(static_file)
        
        # Fallback to index.html for SPA routing
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        
        raise HTTPException(status_code=404, detail="Static content not found")


from app.services.catia_bridge import catia_bridge

# ... existing app and router definitions ...

if __name__ == "__main__":
    import uvicorn
    import sys
    try:
        print("\n" + "="*60)
        print("  CADMation Enterprise for CATIA V5 - Standalone Server")
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
