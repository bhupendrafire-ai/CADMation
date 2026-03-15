import win32com.client
import sys
import os

# Add the project root to sys.path to import app
sys.path.append(os.getcwd())

from app.services.geometry_service import geometry_service

def test_round_detection():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        
        # We'll test on the active document if it's a part, or the first part child
        target = None
        if ".CATPart" in active_doc.Name:
            target = active_doc.Part
        else:
            def find_part(prod):
                try:
                    ref_doc = prod.ReferenceProduct.Parent
                    if ".CATPart" in ref_doc.Name: return ref_doc.Part
                except: pass
                for i in range(1, prod.Products.Count + 1):
                    res = find_part(prod.Products.Item(i))
                    if res: return res
                return None
            target = find_part(active_doc.Product)

        if not target:
            print("No part found to test.")
            return

        print(f"Testing round detection on: {target.Parent.Name}")
        
        # Run the measurement
        res = geometry_service.get_bounding_box(target, fast_mode=False)
        
        print(f"\nMeasurement Result:")
        print(f"  Stock Size: {res.get('stock_size')}")
        print(f"  Is Round? : {res.get('is_round', False)}")
        
        if "DIA" in res.get('stock_size', ''):
            print("\nSUCCESS: 'DIA' prefix detected!")
        else:
            print("\nINFO: Rectangle detection (Normal behavior for plates)")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_round_detection()
