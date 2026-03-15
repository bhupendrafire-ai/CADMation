# CADMation v2.0.0

Local AI copilot for CATIA V5 sheet metal design.

## Features
- **Deep Specification Tree**: Automated extraction of Product/Part structures, Bodies, Shapes, and Parameters.
- **Interactive Tagging**: Tag CATIA components directly from the tree to guide AI focus.
- **Smart Chat Window**: Automatic insertion of tagged components into the chat cursor position.
- **Session Memory**: Multi-turn conversation support for complex design workflows.
- **Standalone Executable**: Single-file distribution for easy local use.
- **Accurate BOM Extraction (v2.0.0)**: Multi-body bounding box union for precise stock sizes, including CATProduct sub-assembly support and hyper-robust SPA tracking.
- **Improved Measurement Reliability (v2.0.0)**: Non-destructive "Context Breaker" strategy for reliable STEP file measurement without session corruption.
- **STD/MFG Classification**: Toggle parts as Standard or Manufactured in the BOM editor; exports to separate Excel worksheets.

## Installation
1. Ensure **CATIA V5** is installed and running.
2. Download the latest `CADMation_Copilot.exe` from the Releases (or build it yourself).
3. Run the executable and open `http://localhost:8000` in your browser.

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

## License
MIT
