import win32com.client
from app.services.catia_bridge import catia_bridge
import math

def test_open_and_measure_main():
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
    print(f"Opening: {part_path}")
    
    docs = caa.Documents
    part_doc = docs.Open(part_path)
    
    try:
        part = part_doc.Part
        spa = part_doc.GetWorkbench("SPAWorkbench")
        
        m = spa.GetMeasurable(part.MainBody)
        b = [0.0]*6
        m.GetBoundaryBox(b)
        dx = abs(b[3]-b[0])*1000
        dy = abs(b[4]-b[1])*1000
        dz = abs(b[5]-b[2])*1000
        print(f"MainBody AABB: {dx:.1f} x {dy:.1f} x {dz:.1f}")
        
        b2 = [0.0]*9
        m.GetMinimumBoundingBox(b2)
        d12 = math.sqrt((b2[3]-b2[0])**2 + (b2[4]-b2[1])**2 + (b2[5]-b2[2])**2)*1000
        d13 = math.sqrt((b2[6]-b2[0])**2 + (b2[7]-b2[1])**2 + (b2[8]-b2[2])**2)*1000
        print(f"MainBody OOBB base: {d12:.1f} x {d13:.1f}")
        
    except Exception as e:
        print(f"Failed: {e}")
        
    part_doc.Close()

test_open_and_measure_main()
