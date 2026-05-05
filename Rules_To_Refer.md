# Rules To Refer: Rough Stock Measurement

This document contains the definitive, proven logic for Rough Stock selection and measurement in CATIA. **DO NOT MODIFY** these rules unless a fundamental change in CATIA behavior is observed.

## 1. Selection Hierarchy (Shallow Traversal)
- **STRICT DEPTH**: Product -> Part -> Body -> STOP.
- Do **NOT** recurse into sub-assemblies or children of bodies.
- Only measure components directly contained within the target CATPart.

## 2. Structural Root Detection (The "Anti-Operand" Rule)
- **NO Name-Based Filtering**: Do not filter by keywords like "MAIN_BODY" or "STOCK".
- **LOGIC**: Identify "Root" bodies by scanning all shapes in the Part. A Body is a "Root" if it is **NOT** used as an operand in any Boolean operations (Add, Remove, Intersect, Assemble) within the same part.
- **GEOMETRY CHECK**: Only select bodies with a non-zero bounding box (detectable via `SPAWorkbench.GetMeasurable`).

## 3. The Selection Trigger (Forceful Selection)
- **NO CLICKS**: Do not attempt to click the "Select" button or any input fields in the Rough Stock dialog. This is flakey and unreliable.
- **DIRECT SEARCH**: Use `Selection.Search(f"Name='{body.Name}',all")` once the dialog is open. This method is the ONLY reliable way to trigger the Rough Stock dimension calculation agent.
- **WAIT TIME**: Give CATIA at least **2.0 seconds** after selection before attempting to scrape dimensions.

## 4. UI Scraping & Robustness
- **WINDOW RESTORE**: Always call `ShowWindow(hw, SW_RESTORE)` and `SetForegroundWindow(hw)` before scraping. Minimized dialogs often report `0mm`.
- **EXHAUSTIVE SCRAPING**: Scrape ALL `Edit` controls in the dialog.
    - Standard Indices: 2 (DX), 5 (DY), 8 (DZ).
    - Fallback: If standard indices are zero, take the **3 largest non-zero values** found in all `Edit` controls.
- **PARSING**: Always use `WM_GETTEXT` with a unicode buffer for reliable MM extraction.

## 5. Background Monitor
- Always use a background thread to monitor for the Rough Stock dialog handle (`hw`) immediately after triggering the command `c:Creates rough stock`.
