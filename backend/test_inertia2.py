import win32com.client
from app.services.catia_bridge import catia_bridge
import math

def test_inertia():
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
    
    print("\n--- INERTIA TEST ---")
    for i in range(1, part.Bodies.Count + 1):
        body = part.Bodies.Item(i)
        try:
            ref = part.CreateReferenceFromObject(body)
            inertia = spa.GetInertia(ref)
            
            bbox = [0.0]*6
            inertia.GetBoundingBox(bbox)
            dx = abs(bbox[1]-bbox[0])*1000
            dy = abs(bbox[3]-bbox[2])*1000
            dz = abs(bbox[5]-bbox[4])*1000
            
            vol = inertia.Mass / inertia.Density * 1e9 if inertia.Density > 0 else 0
            
            print(f"[{i:3d}] {body.Name:30s} | {dx:7.1f} x {dy:7.1f} x {dz:7.1f} | Vol: {vol:10.1f}")
        except Exception as e:
            pass
            
    try:
        ref = part.CreateReferenceFromObject(part.MainBody)
        inertia = spa.GetInertia(ref)
        bbox = [0.0]*6
        inertia.GetBoundingBox(bbox)
        dx = abs(bbox[1]-bbox[0])*1000
        dy = abs(bbox[3]-bbox[2])*1000
        dz = abs(bbox[5]-bbox[4])*1000
        print(f"\nMAIN_BODY Inertia BBox: {dx:.1f} x {dy:.1f} x {dz:.1f}")
        
        m = spa.GetMeasurable(part.MainBody)
        b = [0.0]*6
        m.GetBoundaryBox(b)
        dx2 = abs(b[3]-b[0])*1000
        dy2 = abs(b[4]-b[1])*1000
        dz2 = abs(b[5]-b[2])*1000
        print(f"MAIN_BODY Measurable AABB: {dx2:.1f} x {dy2:.1f} x {dz2:.1f}")
        
        b2 = [0.0]*9
        m.GetMinimumBoundingBox(b2)
        d12 = math.sqrt((b2[3]-b2[0])**2 + (b2[4]-b2[1])**2 + (b2[5]-b2[2])**2)*1000
        d13 = math.sqrt((b2[6]-b2[0])**2 + (b2[7]-b2[1])**2 + (b2[8]-b2[2])**2)*1000
        print(f"MAIN_BODY Measurable OOBB plane: {d12:.1f} x {d13:.1f}")
        
    except Exception as e:
        print(f"MainBody check failed: {e}")

    part_doc.Close()

test_inertia()
