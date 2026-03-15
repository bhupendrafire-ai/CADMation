import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def test_product_measurable():
    caa = catia_bridge.get_application()
    if not caa: return
    
    doc = caa.ActiveDocument
    root = doc.Product
    
    # Let's take the first child of root
    if root.Products.Count == 0:
        print("Root has no children")
        return
        
    child = root.Products.Item(1)
    print(f"Testing child: {child.Name}")
    
    try:
        spa = doc.GetWorkbench("SPAWorkbench")
        measurable = spa.GetMeasurable(child)
        print("  GetMeasurable(child) SUCCESS")
        
        bbox = [0.0]*6
        measurable.GetBoundaryBox(bbox)
        print(f"  BoundaryBox: {bbox}")
        
        dx = abs(bbox[3]-bbox[0])*1000
        dy = abs(bbox[4]-bbox[1])*1000
        dz = abs(bbox[5]-bbox[2])*1000
        print(f"  Result: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
        
    except Exception as e:
        print(f"  GetMeasurable(child) FAILED: {e}")

if __name__ == "__main__":
    test_product_measurable()
