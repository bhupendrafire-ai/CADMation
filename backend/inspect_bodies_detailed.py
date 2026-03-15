import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def inspect_bodies_detailed():
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
    
    try:
        ref_prod = target.ReferenceProduct
        ref_doc = ref_prod.Parent
        if not hasattr(ref_doc, "Part"):
            print("Not a CATPart")
            return
            
        part = ref_doc.Part
        spa = ref_doc.GetWorkbench("SPAWorkbench")
        
        print(f"Total Bodies: {part.Bodies.Count}")
        for i in range(1, part.Bodies.Count + 1):
            body = part.Bodies.Item(i)
            print(f"\nBody {i}: {body.Name}")
            try:
                # Check Visibility
                selection = ref_doc.Selection
                selection.Clear()
                selection.Add(body)
                vis = selection.VisProperties.GetShow()
                # 0 = Show, 1 = NoShow
                print(f"  Visibility: {'SHOW' if vis == 0 else 'NO-SHOW'}")
                
                measurable = spa.GetMeasurable(body)
                bbox = [0.0]*6
                measurable.GetBoundaryBox(bbox)
                dx = abs(bbox[3]-bbox[0])*1000
                dy = abs(bbox[4]-bbox[1])*1000
                dz = abs(bbox[5]-bbox[2])*1000
                print(f"  Size: {dx:.1f} x {dy:.1f} x {dz:.1f}")
                
                # Check Volume
                vol = measurable.Volume
                print(f"  Volume: {vol:.6f} m3")
                
            except Exception as e:
                print(f"  FAILED: {e}")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    inspect_bodies_detailed()
