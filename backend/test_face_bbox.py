import win32com.client
from app.services.catia_bridge import catia_bridge

def face_level_bbox():
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
    
    print("\nAttempting Face-Level BBox on MainBody...")
    
    try:
        sel = part_doc.Selection
        sel.Clear()
        sel.Add(part.MainBody)
        sel.Search("Topology.Face,sel")
        
        count = sel.Count
        print(f"Found {count} Faces in MainBody.")
        
        if count == 0:
            print("No faces found.")
            part_doc.Close()
            return
            
        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        
        success = 0
        for i in range(1, count + 1):
            face_ref = sel.Item(i).Reference
            try:
                m = spa.GetMeasurable(face_ref)
                b = [0.0]*6
                m.GetBoundaryBox(b)
                
                xmin = min(xmin, b[0], b[3])
                ymin = min(ymin, b[1], b[4])
                zmin = min(zmin, b[2], b[5])
                
                xmax = max(xmax, b[0], b[3])
                ymax = max(ymax, b[1], b[4])
                zmax = max(zmax, b[2], b[5])
                
                success += 1
            except Exception as e:
                pass
                
        sel.Clear()
        
        if success > 0:
            dx = (xmax - xmin) * 1000
            dy = (ymax - ymin) * 1000
            dz = (zmax - zmin) * 1000
            print(f"Face Union BBox (Measured {success}/{count}): {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
        else:
            print("Failed to measure any faces.")
            
    except Exception as e:
        print(f"Search/Measure Failed: {e}")
        
    part_doc.Close()

face_level_bbox()
