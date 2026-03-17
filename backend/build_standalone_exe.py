"""
build_standalone_exe.py — One-click standalone EXE builder

Builds a single-file EXE that:
- serves the bundled React frontend (frontend/dist) via FastAPI static mounting
- starts the backend server (uvicorn)
- opens the browser to the local UI
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
    backend_dir = os.path.join(repo, "backend")
    frontend_dir = os.path.join(repo, "frontend")
    frontend_dist = os.path.join(frontend_dir, "dist")

    if not os.path.exists(frontend_dir):
        raise SystemExit(f"Frontend folder not found: {frontend_dir}")

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

    entry = os.path.join(backend_dir, "standalone_entry.py")
    if not os.path.exists(entry):
        raise SystemExit(f"Missing entry script: {entry}")

    add_data = f"{frontend_dist};frontend/dist"
    name = os.environ.get("CADMATION_EXE_NAME", "CADMation_Standalone")

    args = [
        entry,
        "--onefile",
        "--name",
        name,
        f"--add-data={add_data}",
        "--collect-all=uvicorn",
        "--collect-all=fastapi",
        "--collect-all=pydantic",
        "--collect-all=pydantic_settings",
        "--hidden-import=app.routers.catia",
        "--hidden-import=app.routers.chat",
        "--hidden-import=app.services.catia_bridge",
        "--hidden-import=app.services.tree_extractor",
        "--hidden-import=app.services.llm_engine",
        "--hidden-import=app.services.rough_stock_service",
        "--hidden-import=app.services.geometry_service",
        "--hidden-import=app.services.bom_service",
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

    print("--- Starting Standalone EXE build ---")
    print(f"Repo: {repo}")
    print(f"Frontend dist: {frontend_dist}")
    print(f"Entry: {entry}")
    print(f"Name: {name}")
    print(f"Args: {' '.join(args)}")

    PyInstaller.__main__.run(args)

    dist_dir = os.path.join(backend_dir, "dist")
    out_exe = os.path.join(dist_dir, f"{name}.exe")
    if os.path.exists(out_exe):
        root_dist = os.path.join(repo, "dist")
        os.makedirs(root_dist, exist_ok=True)
        shutil.copy2(out_exe, os.path.join(root_dist, os.path.basename(out_exe)))
        print(f"EXE written to: {out_exe}")
        print(f"Copied to: {os.path.join(root_dist, os.path.basename(out_exe))}")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("This standalone EXE builder is intended for Windows.")
    main()

