import win32com.client
from app.services.catia_bridge import catia_bridge
import time

def vertex_bbox():
    caa = catia_bridge.get_application()
    doc = caa.ActiveDocument
    root = doc.Product
    
    def find_prod(p, name):
        if name.upper() in p.Name.upper(): return p
        try:
            for i in range(1, p.Products.Count + 1):
                res = find_prod(p.Products.Item(i), name)
                if res: return res
        except: pass
        return None
        
    target = find_prod(root, "001_LOWER SHOE")
    if not target: return
    
    ref_doc = target.ReferenceProduct.Parent
    part_path = ref_doc.FullName
    part_doc = caa.Documents.Open(part_path)
    part = part_doc.Part
    spa = part_doc.GetWorkbench("SPAWorkbench")
    
    print("\nAttempting Vertex Extraction on MainBody...")
    
    try:
        sel = part_doc.Selection
        sel.Clear()
        sel.Add(part.MainBody)
        sel.Search("Topology.Vertex,sel")
        
        count = sel.Count
        print(f"Found {count} Vertices.")
        
        if count == 0:
            print("No vertices found.")
            part_doc.Close()
            return
            
        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        
        success = 0
        for i in range(1, count + 1):
            v_ref = sel.Item(i).Reference
            try:
                m = spa.GetMeasurable(v_ref)
                pt = [0.0, 0.0, 0.0]
                m.GetPoint(pt)
                
                x, y, z = pt[0], pt[1], pt[2]
                xmin = min(xmin, x)
                ymin = min(ymin, y)
                zmin = min(zmin, z)
                
                xmax = max(xmax, x)
                ymax = max(ymax, y)
                zmax = max(zmax, z)
                
                success += 1
            except Exception as pe:
                pass
                
        sel.Clear()
        
        if success > 0:
            dx = (xmax - xmin) * 1000
            dy = (ymax - ymin) * 1000
            dz = (zmax - zmin) * 1000
            print(f"Vertex BBox ({success}/{count}): {dx:.3f} x {dy:.3f} x {dz:.3f} mm")
        else:
            print("Failed to measure any vertices.")
            
    except Exception as e:
        print(f"Failed: {e}")
        
    part_doc.Close()

vertex_bbox()
