"""
Single entry point: builds the frontend if needed, then starts FastAPI + Qt shell.
Run: python run_cadmation.py (from any cwd; repo root is inferred from this file).
"""
from __future__ import annotations

import os
import subprocess
import sys


def _repo_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _ensure_frontend_dist(repo: str) -> None:
    dist_index = os.path.join(repo, "frontend", "dist", "index.html")
    if os.path.isfile(dist_index):
        return
    frontend = os.path.join(repo, "frontend")
    if not os.path.isdir(frontend):
        sys.exit(f"Missing frontend folder: {frontend}")
    print("Building frontend (first run or dist missing)...")
    try:
        subprocess.run(["npm", "install"], cwd=frontend, check=True)
        subprocess.run(["npm", "run", "build"], cwd=frontend, check=True)
    except FileNotFoundError:
        sys.exit(
            "Node.js/npm not found. Install Node.js, then run:\n"
            f"  cd {frontend}\n"
            "  npm install && npm run build\n"
            "Then run this script again."
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"Frontend build failed (exit {e.returncode}). Fix errors above and retry.")


def main() -> None:
    repo = _repo_root()
    backend = os.path.join(repo, "backend")
    if not os.path.isdir(backend):
        sys.exit(f"Expected backend at {backend}")

    _ensure_frontend_dist(repo)

    os.chdir(backend)
    if backend not in sys.path:
        sys.path.insert(0, backend)

    import gui  # noqa: E402 — after path/cwd so `app` resolves

    gui.main()


if __name__ == "__main__":
    main()
