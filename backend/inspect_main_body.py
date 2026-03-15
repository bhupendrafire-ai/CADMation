import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def inspect_main_body():
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
        ref_doc = target.ReferenceProduct.Parent
        part = ref_doc.Part
        spa = ref_doc.GetWorkbench("SPAWorkbench")
        
        # PartBody
        print(f"\nMAIN BODY (PartBody): {part.PartBody.Name}")
        m = spa.GetMeasurable(part.PartBody)
        b = [0.0]*6
        m.GetBoundaryBox(b)
        dx = abs(b[3]-b[0])*1000
        dy = abs(b[4]-b[1])*1000
        dz = abs(b[5]-b[2])*1000
        print(f"  Size: {dx:.1f} x {dy:.1f} x {dz:.1f}")

        # Check all visible bodies
        print("\nVISIBLE BODIES:")
        count = 0
        for i in range(1, part.Bodies.Count + 1):
            body = part.Bodies.Item(i)
            # Visibility check
            ref_doc.Selection.Clear()
            ref_doc.Selection.Add(body)
            vis = ref_doc.Selection.VisProperties.GetShow()
            if vis == 0: # SHOW
                count += 1
                try:
                    m = spa.GetMeasurable(body)
                    b = [0.0]*6
                    m.GetBoundaryBox(b)
                    dx = abs(b[3]-b[0])*1000
                    dy = abs(b[4]-b[1])*1000
                    dz = abs(b[5]-b[2])*1000
                    print(f"  [{i}] {body.Name}: {dx:.1f} x {dy:.1f} x {dz:.1f}")
                except:
                    print(f"  [{i}] {body.Name}: Measurement failed")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    inspect_main_body()
