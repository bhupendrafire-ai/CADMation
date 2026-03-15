import logging
import sys
import os

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service

logging.basicConfig(level=logging.INFO)

def verify():
    print("--- Verifying GeometryService ---")
    caa = catia_bridge.get_application()
    if not caa:
        print("Error: CATIA not found.")
        return

    doc = caa.ActiveDocument
    print(f"Active Document: {doc.Name}")
    
    if not hasattr(doc, "Part"):
        # Try to find a part in the session if active is not a part
        part_doc = None
        for i in range(1, caa.Documents.Count + 1):
            d = caa.Documents.Item(i)
            if ".CATPart" in d.Name:
                part_doc = d
                break
        if not part_doc:
            print("No CATPart found in session.")
            return
        doc = part_doc
        print(f"Using Found Part: {doc.Name}")

    part = doc.Part
    bbox = geometry_service.get_bounding_box(part)
    print(f"Bounding Box Result: {bbox}")
    
    if "x" in bbox and bbox["x"] != 50.0:
        print("SUCCESS: Real dimensions retrieved.")
    else:
        print("WARNING: Falling back to placeholders or estimation.")

if __name__ == "__main__":
    verify()
