import win32com.client
from app.services.catia_bridge import catia_bridge

def search_lower_shoe():
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
    if not target:
        print("Not found")
        return
        
    print(f"Found: {target.Name}")
    try:
        ref_doc = target.ReferenceProduct.Parent
        part = ref_doc.Part
        spa = ref_doc.GetWorkbench("SPAWorkbench")
        
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
                print(f"[{i:3d}] {body.Name:30s} | Vol: {v:.4f} | BBox: {dx:.1f} x {dy:.1f} x {dz:.1f}")
            except Exception as e:
                print(f"[{i:3d}] {body.Name:30s} | Fail: {e}")
    except Exception as e:
        print(f"Error accessing Part: {e}")

search_lower_shoe()
