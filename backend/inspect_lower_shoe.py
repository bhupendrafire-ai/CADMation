import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def inspect_lower_shoe():
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
    if not target:
        print(f"Could not find {target_name}")
        return
        
    print(f"INSPECTING: {target.Name}")
    print(f"Child Count: {target.Products.Count}")
    
    for i in range(1, target.Products.Count + 1):
        child = target.Products.Item(i)
        print(f"\n[{i}] Child Name: {child.Name}")
        try:
            ref_prod = child.ReferenceProduct
            print(f"    Ref Name: {ref_prod.Name}")
            ref_doc = ref_prod.Parent
            print(f"    Ref Doc: {ref_doc.Name}")
            
            # Check for Part
            is_part = hasattr(ref_doc, "Part")
            print(f"    Is Part: {is_part}")
            
            if is_part:
                part = ref_doc.Part
                print(f"    Bodies: {part.Bodies.Count}")
                spa = ref_doc.GetWorkbench("SPAWorkbench")
                for j in range(1, part.Bodies.Count + 1):
                    body = part.Bodies.Item(j)
                    measurable = spa.GetMeasurable(body)
                    bbox = [0.0]*6
                    measurable.GetBoundaryBox(bbox)
                    dx = abs(bbox[3]-bbox[0])*1000
                    dy = abs(bbox[4]-bbox[1])*1000
                    dz = abs(bbox[5]-bbox[2])*1000
                    print(f"      Body {j} ({body.Name}): {dx:.1f} x {dy:.1f} x {dz:.1f}")

        except Exception as e:
            print(f"    ERROR: {e}")

if __name__ == "__main__":
    inspect_lower_shoe()
