
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "app"))
# Mocking catia_bridge if needed, but we want to use the real one
from app.services.geometry_service import GeometryService
import win32com.client
import pythoncom

logging.basicConfig(level=logging.INFO)

def test_production_surgical():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        target_body_name = "LOWER STEEL_1"
        
        # 1. Find the target object reference
        target_obj = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if hasattr(doc, "Part"):
                for b in doc.Part.Bodies:
                    if target_body_name.lower() in b.Name.lower():
                        target_obj = b
                        break
            if target_obj: break
        
        if not target_obj:
            print(f"FAILED: Could not find {target_body_name} in open docs.")
            return

        print(f"Target Resolved: {target_obj.Name} in {target_obj.Parent.Parent.Name}")
        
        # 2. Trigger the production service
        service = GeometryService()
        print("Measuring via GeometryService...")
        result = service.get_bounding_box(target_obj)
        
        print("\nRESULT:")
        print(result)
        
        if result and result.get("x", 0) > 0.1:
            print("\n!!! PRODUCTION VERIFICATION SUCCESS !!!")
        else:
            print("\nFAILED: Measurement returned invalid or fallback result.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_production_surgical()
