import win32com.client
from app.services.catia_bridge import catia_bridge

def test_ref_mainbody():
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
    part = ref_doc.Part
    spa = ref_doc.GetWorkbench("SPAWorkbench")
    
    try:
        ref = part.CreateReferenceFromObject(part.MainBody)
        m = spa.GetMeasurable(ref)
        b = [0.0]*6
        m.GetBoundaryBox(b)
        dx = abs(b[3]-b[0])*1000
        dy = abs(b[4]-b[1])*1000
        dz = abs(b[5]-b[2])*1000
        print(f"MainBody AABB: {dx:.1f} x {dy:.1f} x {dz:.1f}")
    except Exception as e:
        print(f"Failed: {e}")

test_ref_mainbody()
