import win32com.client
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.geometry_service import geometry_service

def test_assembly_logic():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        
        main_prod = active_doc.Product
        print(f"Active Assembly: {main_prod.Name}")
        
        # 1. Test measurement of the WHOLE assembly
        print("\n--- Measuring Main Assembly ---")
        res = geometry_service.get_bounding_box(main_prod, fast_mode=True)
        print(f"Result: {res.get('stock_size')}")

        # 2. Try to find a sub-assembly
        def find_sub_assy(p):
            try:
                if p.Products.Count > 0: return p
                for i in range(1, p.Products.Count + 1):
                    res = find_sub_assy(p.Products.Item(i))
                    if res: return res
            except: pass
            return None

        # Find first sub-product with children
        sub_assy = None
        for i in range(1, main_prod.Products.Count + 1):
            p = main_prod.Products.Item(i)
            if p.Products.Count > 0:
                sub_assy = p
                break
        
        if sub_assy:
            print(f"\n--- Measuring Sub-Assembly: {sub_assy.Name} ---")
            res = geometry_service.get_bounding_box(sub_assy, fast_mode=True)
            print(f"Result: {res.get('stock_size')}")
        else:
            print("\nNo sub-assembly with children found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_assembly_logic()
