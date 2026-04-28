"""
build_gui_exe.py — Native GUI standalone EXE builder

Builds a single-file EXE that:
- starts the backend server in-process
- opens a native Qt window (QWebEngineView) pointing at http://127.0.0.1:8000
- serves the bundled React frontend from frontend/dist via FastAPI static mount
"""

import os
import shutil
import subprocess
import sys


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(cmd: list[str], cwd: str):
    print(f"> {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd)


def main():
    repo = _repo_root()
    os.chdir(repo)
    backend_dir = os.path.join(repo, "backend")
    frontend_dir = os.path.join(repo, "frontend")
    frontend_dist = os.path.join(frontend_dir, "dist")
    dist_out = os.path.join(repo, "dist")
    work_out = os.path.join(repo, "build", "pyinstaller_gui")

    if not os.path.exists(frontend_dist):
        print("Frontend 'dist' not found. Building frontend first.")
        _run(["npm", "install"], cwd=frontend_dir)
        _run(["npm", "run", "build"], cwd=frontend_dir)

    try:
        import PyInstaller.__main__  # type: ignore
    except Exception:
        print("PyInstaller not found. Install it in your backend venv first:")
        print("  pip install pyinstaller")
        raise

    gui_entry = os.path.join(backend_dir, "gui.py")
    icon_path = os.path.join(backend_dir, "resources", "app_icon.ico")
    resources_dir = os.path.join(backend_dir, "resources")
    
    name = os.environ.get("CADMATION_GUI_EXE_NAME", "CADMation_GUI")

    args = [
        gui_entry,
        "--onefile",
        "--noconsole",
        "--name",
        name,
        "--icon",
        icon_path,
        "--distpath",
        dist_out,
        "--workpath",
        work_out,
        "--specpath",
        work_out,
        "--paths",
        backend_dir,
        "--add-data",
        f"{frontend_dist};frontend/dist",
        "--add-data",
        f"{resources_dir};resources",
        "--collect-all=uvicorn",
        "--collect-all=fastapi",
        "--collect-all=pydantic",
        "--collect-all=pydantic_settings",
        "--hidden-import=PySide6",
        "--hidden-import=shiboken6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtNetwork",
        "--hidden-import=PySide6.QtWebChannel",
        "--hidden-import=PySide6.QtWebEngineCore",
        "--hidden-import=PySide6.QtWebEngineWidgets",
        "--hidden-import=PySide6.QtPrintSupport",
        "--hidden-import=app.routers.catia",
        "--hidden-import=app.routers.chat",
        "--hidden-import=app.services.catia_bridge",
        "--hidden-import=app.services.tree_extractor",
        "--hidden-import=app.services.llm_engine",
        "--hidden-import=app.services.rough_stock_service",
        "--hidden-import=app.services.geometry_service",
        "--hidden-import=app.services.bom_service",
        "--hidden-import=app.services.history_service",
        "--hidden-import=app.services.skill_service",
        "--hidden-import=app.services.memory_service",
        "--hidden-import=app.services.drafting_service",
        "--hidden-import=app.services.bom_rules",
        "--hidden-import=app.services.bom_schema",
        "--hidden-import=app.config",
        "--hidden-import=app.debug_agent_log",
        "--hidden-import=app.services.body_name_disambiguation_service",
        "--hidden-import=app.services.catia_bom_resolve",
        "--hidden-import=app.services.drafting_axis_resolve",
        "--hidden-import=app.services.drafting_axis_propagate",
        "--hidden-import=app.services.bom_cache_service",
        "--hidden-import=app.services.com_worker",
        "--hidden-import=app.services.drafting_orientation",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.protocols.http.h11_impl",
        "--hidden-import=uvicorn.protocols.http.httptools_impl",
        "--hidden-import=uvicorn.protocols.websockets.websockets_impl",
        "--hidden-import=uvicorn.protocols.websockets.wsproto_impl",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.lifespan.off",
        "--clean",
        "--noconfirm",
    ]

    print("--- Starting Native GUI EXE build ---")
    print(f"Repo: {repo}")
    print(f"Frontend dist: {frontend_dist}")
    print(f"Entry: {gui_entry}")
    print(f"Name: {name}")

    os.makedirs(dist_out, exist_ok=True)
    os.makedirs(work_out, exist_ok=True)
    PyInstaller.__main__.run(args)

    produced = os.path.join(dist_out, f"{name}.exe")
    if os.path.exists(produced):
        print(f"EXE written to: {produced}")
        return

    backend_dist = os.path.join(backend_dir, "dist", f"{name}.exe")
    if os.path.exists(backend_dist):
        shutil.copy2(backend_dist, produced)
        print(f"EXE copied to: {produced}")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("This GUI EXE builder is intended for Windows.")
    main()

