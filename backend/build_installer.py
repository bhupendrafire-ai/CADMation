"""
build_installer.py — Standalone CADMation Bundler

Uses PyInstaller to package the FastAPI backend and bundled React frontend
into a single executable (.exe).
"""

import PyInstaller.__main__
import os
import shutil

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "dist"))
MAIN_SCRIPT = os.path.join(BASE_DIR, "app", "main.py")

print(f"--- Starting Build Process ---")
print(f"Base Directory: {BASE_DIR}")
print(f"Frontend Dist: {FRONTEND_DIST}")

if not os.path.exists(FRONTEND_DIST):
    print("ERROR: Frontend 'dist' folder not found. Run 'npm run build' in the frontend directory first.")
    exit(1)

# PyInstaller Arguments
args = [
    MAIN_SCRIPT,
    "--onefile",                                # Pack everything into one exe
    "--name=CADMation_Copilot",                 # Output file name
    f"--add-data={FRONTEND_DIST};frontend/dist", # Include frontend files (Note: ';' for Windows)
    "--collect-all=uvicorn",                   # Include uvicorn and its deps
    "--collect-all=fastapi",                   # Include fastapi and its deps
    "--hidden-import=app.routers.catia",
    "--hidden-import=app.routers.chat",
    "--hidden-import=app.services.catia_bridge",
    "--hidden-import=app.services.tree_extractor",
    "--hidden-import=app.services.llm_engine",
    "--clean",
    "--noconfirm"
]

print(f"Running PyInstaller with args: {' '.join(args)}")

PyInstaller.__main__.run(args)

print("\n--- Build Complete! ---")
print("Standalone executable can be found in the 'dist' folder.")
