import win32com.client
from app.services.catia_bridge import catia_bridge
import math

def test_measure_base_body():
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
    
    print(f"Opening Part: {part_path}")
    part_doc = caa.Documents.Open(part_path)
    part = part_doc.Part
    spa = part_doc.GetWorkbench("SPAWorkbench")
    
    try:
        # Find BASE_BODY
        base_body = None
        for i in range(1, part.Bodies.Count + 1):
            if part.Bodies.Item(i).Name == "BASE_BODY":
                base_body = part.Bodies.Item(i)
                break
                
        if not base_body:
            print("BASE_BODY not found")
        else:
            print("Found BASE_BODY. Measuring...")
            try:
                ref = part.CreateReferenceFromObject(base_body)
                m = spa.GetMeasurable(ref)
                b = [0.0]*6
                m.GetBoundaryBox(b)
                dx = abs(b[3]-b[0])*1000
                dy = abs(b[4]-b[1])*1000
                dz = abs(b[5]-b[2])*1000
                print(f"AABB [BASE_BODY]: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
                
            except Exception as e:
                print(f"Failed via reference: {e}")
                
            try:
                # Try direct
                m = spa.GetMeasurable(base_body)
                b = [0.0]*6
                m.GetBoundaryBox(b)
                dx = abs(b[3]-b[0])*1000
                dy = abs(b[4]-b[1])*1000
                dz = abs(b[5]-b[2])*1000
                print(f"AABB [Direct BASE_BODY]: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
            except Exception as e:
                print(f"Failed via direct body: {e}")
                
    except Exception as e:
        print(f"Error checking bodies: {e}")
        
    part_doc.Close()

test_measure_base_body()
