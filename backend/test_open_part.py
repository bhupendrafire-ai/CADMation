import win32com.client
from app.services.catia_bridge import catia_bridge

def test_open_part_measure():
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
    print(f"Part Path: {part_path}")
    
    # Open the part in a new window
    try:
        docs = caa.Documents
        part_doc = docs.Open(part_path)
        print("Successfully opened part document.")
        
        part = part_doc.Part
        spa = part_doc.GetWorkbench("SPAWorkbench")
        
        for i in range(1, part.Bodies.Count + 1):
            body = part.Bodies.Item(i)
            try:
                m = spa.GetMeasurable(body)
                v = m.Volume
                b = [0.0]*6
                m.GetBoundaryBox(b)
                dx = abs(b[3]-b[0])*1000
                dy = abs(b[4]-b[1])*1000
                dz = abs(b[5]-b[2])*1000
                print(f"[{i:3d}] {body.Name:30s} | Vol: {v*1e9:12.1f} | BBox: {dx:.1f} x {dy:.1f} x {dz:.1f}")
            except Exception as e:
                pass # print(f"[{i:3d}] {body.Name:30s} | Fail: {e}")
                
        # Close the document
        part_doc.Close()
        print("Closed part document.")
        
    except Exception as e:
        print(f"Error opening/measuring part: {e}")

test_open_part_measure()
