import win32com.client
import sys
import os
import shutil
import time

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from app.services.geometry_service import geometry_service

def measure_stl_confirmed():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        def find_product(prod, name):
            if name.upper() in prod.Name.upper() or name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_product(prod.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        target = find_product(doc.Product, "202_LOWER PLATE")
        if not target:
            print("Target 202_LOWER PLATE not found.")
            return

        print(f"Measuring {target.Name} via STL...")
        
        # We'll use the geometry_service._measure_via_stl_full directly to avoid assembly recursion problems
        # or use get_bounding_box with method='STL'
        geometry_service.clear_cache()
        res = geometry_service.get_bounding_box(target, method="STL")
        
        print(f"\nSTL RESULTS:")
        print(f"X: {res.get('x')} mm")
        print(f"Y: {res.get('y')} mm")
        print(f"Z: {res.get('z')} mm")
        print(f"Stock size: {res.get('stock_size')}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_stl_confirmed()
