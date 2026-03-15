import logging
import sys
import os
import time

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

logging.basicConfig(level=logging.INFO)

def research_selection_bbox():
    target_name = "001_LOWER SHOE"
    
    caa = catia_bridge.get_application()
    if not caa: 
        print("No CATIA")
        return
        
    doc = caa.ActiveDocument
    root = doc.Product
    
    def find_prod(p, name):
        if name.upper() in p.Name.upper(): return p
        for i in range(1, p.Products.Count + 1):
            res = find_prod(p.Products.Item(i), name)
            if res: return res
        return None
        
    target = find_prod(root, target_name)
    if not target:
        print(f"Could not find {target_name}")
        return
        
    print(f"Found: {target.Name}")
    
    # Selection-based BBox
    try:
        selection = doc.Selection
        selection.Clear()
        selection.Add(target)
        
        # In CATIA, Selection.Boundary gives a box but interpreted differently.
        # SPA workbench is better but requires a specific object.
        
        # Let's try SPA on the product's ReferenceProduct
        spa = doc.GetWorkbench("SPAWorkbench")
        measurable = spa.GetMeasurable(target)
        
        bbox = [0.0]*6
        measurable.GetBoundaryBox(bbox)
        print(f"Raw SPA Box (meters): {bbox}")
        
        dx = abs(bbox[3] - bbox[0]) * 1000
        dy = abs(bbox[4] - bbox[1]) * 1000
        dz = abs(bbox[5] - bbox[2]) * 1000
        print(f"SPA Measurable Result: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")

    except Exception as e:
        print(f"Selection/SPA method failed: {e}")

    # Now let's try iterating children and printing details to see why it fails
    print("\n--- Child Detail Check ---")
    try:
        for i in range(1, min(target.Products.Count, 10) + 1):
            child = target.Products.Item(i)
            print(f"Child {i}: {child.Name}")
            try:
                ref_doc = child.ReferenceProduct.Parent
                print(f"  Ref Doc: {ref_doc.Name}")
                is_part = hasattr(ref_doc, "Part")
                print(f"  Is Part: {is_part}")
            except:
                print("  Failed to get Ref Doc details")
    except Exception as e:
        print(f"Iteration failed: {e}")

if __name__ == "__main__":
    research_selection_bbox()
