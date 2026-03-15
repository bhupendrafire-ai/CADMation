import win32com.client
from app.services.catia_bridge import catia_bridge

def test_reference():
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
    
    print(f"Target: {target.Name}")
    
    # Try MainBody without ref
    try:
        m1 = spa.GetMeasurable(part.MainBody)
        print("Success on MainBody direct")
    except Exception as e:
        print(f"MainBody direct failed: {e}")
        
    # Try Body 1 without ref
    try:
        b1 = part.Bodies.Item(1)
        m2 = spa.GetMeasurable(b1)
        print("Success on Body 1 direct")
    except Exception as e:
        print(f"Body 1 direct failed: {e}")

    # Try Body 1 WITH ref
    try:
        b1 = part.Bodies.Item(1)
        ref = part.CreateReferenceFromObject(b1)
        m3 = spa.GetMeasurable(ref)
        print("Success on Body 1 WITH Reference")
        
        b = [0.0]*6
        m3.GetBoundaryBox(b)
        dx = abs(b[3]-b[0])*1000
        dy = abs(b[4]-b[1])*1000
        dz = abs(b[5]-b[2])*1000
        print(f"Body 1 BBox: {dx:.1f} x {dy:.1f} x {dz:.1f}")
        
    except Exception as e:
        print(f"Body 1 WITH Reference failed: {e}")
        
    # Let's try to find the PartBody specifically and measure it
    try:
        part_body = part.PartBody
        ref_pb = part.CreateReferenceFromObject(part_body)
        m_pb = spa.GetMeasurable(ref_pb)
        b = [0.0]*6
        m_pb.GetBoundaryBox(b)
        dx = abs(b[3]-b[0])*1000
        dy = abs(b[4]-b[1])*1000
        dz = abs(b[5]-b[2])*1000
        vol = m_pb.Volume
        print(f"PartBody BBox: {dx:.1f} x {dy:.1f} x {dz:.1f} (Vol: {vol:.5f})")
    except Exception as e:
        print(f"PartBody WITH Reference failed: {e}")

test_reference()
