# CADMation v2.0.0

Local AI copilot for CATIA V5 sheet metal design.

## Features
- **Deep Specification Tree**: Automated extraction of Product/Part structures, Bodies, Shapes, and Parameters.
- **Interactive Tagging**: Tag CATIA components directly from the tree to guide AI focus.
- **Smart Chat Window**: Automatic insertion of tagged components into the chat cursor position.
- **Session Memory**: Multi-turn conversation support for complex design workflows.
- **Standalone Executable**: Single-file distribution for easy local use.
- **Accurate BOM Extraction (v2.0.0)**: Multi-body bounding box union for precise stock sizes, including CATProduct sub-assembly support and hyper-robust SPA tracking.
- **Elective Measurement Methods (v2.1.0)**: Choose between high-speed **Rough Stock** scraping and robust **STL (Nuclear)** isolation directly in the BOM list.
- **Stability and Accuracy (v2.2.0)**: Fixed critical WebSocket crashes, corrected STL bounding box calculation logic, and added robust fallback search for deep assemblies.
- **Robust Part Identification**: Improved PartNumber resolution using reference document names to prevent mismatches from duplicate instance naming.
- **STD/MFG Classification**: Toggle parts as Standard or Manufactured in the BOM editor; exports to separate Excel worksheets.

## Installation
1. Ensure **CATIA V5** is installed and running.
2. Download the latest standalone exe from Releases (or build it yourself).
3. Run the executable. It will start the local server and open the UI automatically.

## Run the full app (one file)
From the repo root, after `pip install -r backend/requirements.txt` in your environment:
```bash
python run_cadmation.py
```
This builds `frontend/dist` via npm if needed, then starts the API and opens the native window.

## Development
### Backend
1. `cd backend`
2. `python -m venv venv`
3. `venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. Create a `.env` file based on `.env.example`.
6. Run: `python -m uvicorn app.main:app --reload`

### Frontend
1. `cd frontend`
2. `npm install`
3. Run: `npm run dev`

## Building a Standalone EXE
- One step (from repo root): run `build_windows_exe.bat` (installs build deps, builds frontend if needed, runs PyInstaller).
- Or manually: `cd frontend` → `npm run build`, then `python backend/build_gui_exe.py` from the repo root (or `cd backend` → `python build_gui_exe.py`).
- Output: `dist/CADMation_GUI.exe` — starts the FastAPI backend and opens the UI in an embedded browser window.

## License
MIT
