import win32com.client
import sys
import os
import logging

# Configure logging to see output
logging.basicConfig(level=logging.DEBUG)

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.geometry_service import geometry_service

def debug_measurement():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        
        target = None
        if ".CATPart" in active_doc.Name:
            target = active_doc.Part
        else:
            def find_part(prod):
                try:
                    ref_doc = prod.ReferenceProduct.Parent
                    if ".CATPart" in ref_doc.Name: return (prod, ref_doc.Part)
                except: pass
                for i in range(1, prod.Products.Count + 1):
                    res = find_part(prod.Products.Item(i))
                    if res: return res
                return (None, None)
            
            prod_inst, target = find_part(active_doc.Product)

        if not target:
            print("No part found.")
            return

        print(f"Targeting Part: {target.Parent.Name}")
        
        # Test STL strategy directly
        print("\n--- Testing STL Strategy ---")
        res_stl = geometry_service._get_stl_bbox_from_part(caa, target)
        if res_stl:
            print(f"STL Success: {res_stl['stock_size']}")
        else:
            print("STL Failed.")

        # Test Full BBox logic
        print("\n--- Testing Full get_bounding_box ---")
        res_full = geometry_service.get_bounding_box(target, fast_mode=False)
        print(f"Full Result: {res_full['stock_size']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_measurement()
