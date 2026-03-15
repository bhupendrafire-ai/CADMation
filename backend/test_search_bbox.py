import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def test_search_bbox():
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
    
    # We need to compute the bbox for this product component
    # The best way: Selection.Search(Name=target_name)
    try:
        selection = doc.Selection
        selection.Clear()
        
        # Search for all bodies inside this part that are visible
        # Note: We need to scope the search to the part
        ref_doc = target.ReferenceProduct.Parent
        part_selection = ref_doc.Selection
        part_selection.Clear()
        part_selection.Search("CATPartSearch.Body.Vis=Visible,all")
        
        count = part_selection.Count
        print(f"Visible bodies found in {target.Name}: {count}")
        
        if count > 0:
            spa = ref_doc.GetWorkbench("SPAWorkbench")
            global_min = [float('inf')] * 3
            global_max = [float('-inf')] * 3
            found = False
            
            for i in range(1, count + 1):
                body = part_selection.Item(i).Value
                try:
                    m = spa.GetMeasurable(body)
                    b = [0.0]*6
                    m.GetBoundaryBox(b)
                    if abs(b[3]-b[0]) > 1e-9:
                        found = True
                        for axis in range(3):
                            global_min[axis] = min(global_min[axis], b[axis])
                            global_max[axis] = max(global_max[axis], b[axis+3])
                        print(f"  Body: {body.Name} -> {abs(b[3]-b[0])*1000:.1f}x{abs(b[4]-b[1])*1000:.1f}x{abs(b[5]-b[2])*1000:.1f}")
                except: pass
                
            if found:
                dx = (global_max[0] - global_min[0]) * 1000
                dy = (global_max[1] - global_min[1]) * 1000
                dz = (global_max[2] - global_min[2]) * 1000
                print(f"\nRESULT: {dx:.1f} x {dy:.1f} x {dz:.1f} mm")
        else:
            print("No visible bodies found via Search.")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_search_bbox()
