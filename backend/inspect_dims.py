import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("h:/CADMation/backend"))

from app.services.catia_bridge import catia_bridge
import logging

def inspect_dimensions():
    caa = catia_bridge.get_application()
    if not caa:
        print("CATIA not found")
        return

    doc = caa.ActiveDocument
    if not doc.Name.endswith(".CATDrawing"):
        print("Please open a CATDrawing")
        return

    sheet = doc.Sheets.ActiveSheet
    view = sheet.Views.ActiveView
    dims = view.Dimensions
    
    print(f"--- Inspecting Dimensions in {view.Name} ---")
    print(f"Total Dimensions: {dims.Count}")
    
    # Try to see methods available on the Dimensions collection
    try:
        # Standard techniques to list members of a COM object in Python are limited 
        # unless we use something like win32com.client.gencache
        import win32com.client
        dims_com = dims.com_object
        print("Members (raw):", dir(dims_com))
    except Exception as e:
        print(f"Error inspecting: {e}")

if __name__ == "__main__":
    inspect_dimensions()
