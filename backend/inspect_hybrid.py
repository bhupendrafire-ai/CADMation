import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def inspect_hybrid_design():
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
    
    ref_doc = target.ReferenceProduct.Parent
    part = ref_doc.Part
    spa = ref_doc.GetWorkbench("SPAWorkbench")
    selection = ref_doc.Selection
    
    print(f"Hybrid Bodies (Geometric Sets): {part.HybridBodies.Count}")
    
    for i in range(1, part.HybridBodies.Count + 1):
        hb = part.HybridBodies.Item(i)
        print(f"\nHB [{i}]: {hb.Name}")
        # Try to find shapes inside HB
        try:
            for j in range(1, hb.HybridShapes.Count + 1):
                shape = hb.HybridShapes.Item(j)
                print(f"  Shape [{j}]: {shape.Name}")
                try:
                    measurable = spa.GetMeasurable(shape)
                    bbox = [0.0]*6
                    measurable.GetBoundaryBox(bbox)
                    dx = abs(bbox[3]-bbox[0])*1000
                    print(f"    Size X: {dx:.1f}")
                except: pass
        except: pass

    # Check for HybridShapes directly in Part
    try:
        print(f"\nPart HybridShapes Count: {part.HybridShapeFactory.Count}")
    except: pass

if __name__ == "__main__":
    inspect_hybrid_design()
