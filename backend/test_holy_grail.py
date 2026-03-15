import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def test_holy_grail():
    target_name = "001_LOWER SHOE"
    caa = catia_bridge.get_application()
    if not caa: return
    
    doc = caa.ActiveDocument
    root = doc.Product
    
    def find_prod(p, name):
        if name.upper() in p.Name.upper(): return p
        for i in range(1, p.Products.Count + 1):
            res = find_prod(p.Products.Item(i), name)
            if res: return res
        return None
        
    target = find_prod(root, target_name)
    if not target: return
    
    print(f"Target: {target.Name}")
    
    try:
        # GET SPA FROM THE ROOT DOCUMENT
        spa = doc.GetWorkbench("SPAWorkbench")
        
        # MEASURE THE PRODUCT OBJECT DIRECTLY
        measurable = spa.GetMeasurable(target)
        print("  GetMeasurable(target) SUCCESS")
        
        bbox = [0.0]*6
        measurable.GetBoundaryBox(bbox)
        print(f"  BoundaryBox: {bbox}")
        
        dx = abs(bbox[3]-bbox[0])*1000
        dy = abs(bbox[4]-bbox[1])*1000
        dz = abs(bbox[5]-bbox[2])*1000
        print(f"  Result: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
        
    except Exception as e:
        print(f"  FAILED: {e}")

if __name__ == "__main__":
    test_holy_grail()
