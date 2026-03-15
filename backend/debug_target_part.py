import win32com.client
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.geometry_service import geometry_service

def test_specific_part():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        
        target_name = "203_UPPER_FLANGE_STEEL_01.1"
        print(f"Searching for: {target_name}")
        
        def find_target(prod, name):
            if prod.Name == name: return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    res = find_target(prod.Products.Item(i), name)
                    if res: return res
            except: pass
            return None

        target_prod = find_target(active_doc.Product, target_name)
        
        if not target_prod:
            print(f"Error: Part '{target_name}' not found in active document '{active_doc.Name}'.")
            return

        print(f"Found target: {target_prod.Name}")
        
        # Test full logic
        print("\n--- Running get_bounding_box ---")
        # Ensure we use fast_mode=False to trigger STL and deep inspection
        res = geometry_service.get_bounding_box(target_prod, fast_mode=False)
        
        print("\nFinal Result:")
        print(f"  Stock Size: {res.get('stock_size')}")
        print(f"  Dimensions: {res.get('x')} x {res.get('y')} x {res.get('z')}")
        print(f"  Is Round? : {res.get('is_round', False)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_specific_part()
