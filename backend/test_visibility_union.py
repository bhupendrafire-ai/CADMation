import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def test_visibility_union():
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
    
    global_min = [float('inf')] * 3
    global_max = [float('-inf')] * 3
    found_any = False
    
    print(f"Inspecting {part.Bodies.Count} bodies for visibility...")
    
    for i in range(1, part.Bodies.Count + 1):
        body = part.Bodies.Item(i)
        selection.Clear()
        selection.Add(body)
        try:
            vis = selection.VisProperties.GetShow()
            if vis == 0: # SHOW
                measurable = spa.GetMeasurable(body)
                bbox = [0.0]*6
                measurable.GetBoundaryBox(bbox)
                
                # Check if box is valid
                dx = abs(bbox[3]-bbox[0])
                if dx > 1e-9:
                    found_any = True
                    print(f"  Body [{i}] {body.Name} is SHOWN. Size: {dx*1000:.1f} x {abs(bbox[4]-bbox[1])*1000:.1f} x {abs(bbox[5]-bbox[2])*1000:.1f}")
                    for axis in range(3):
                        global_min[axis] = min(global_min[axis], bbox[axis])
                        global_max[axis] = max(global_max[axis], bbox[axis+3])
        except: pass
        
    if found_any:
        dx = (global_max[0] - global_min[0]) * 1000
        dy = (global_max[1] - global_min[1]) * 1000
        dz = (global_max[2] - global_min[2]) * 1000
        print(f"\nUNION OF SHOWN BODIES: {dx:.1f} x {dy:.1f} x {dz:.1f} mm")
    else:
        print("\nNo visible bodies found with valid geometry.")

if __name__ == "__main__":
    test_visibility_union()
