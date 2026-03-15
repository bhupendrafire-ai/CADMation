import win32com.client
from app.services.catia_bridge import catia_bridge
import math

def test_oobb_all():
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
    
    print("Testing GetMinimumBoundingBox on all bodies reference:")
    for i in range(1, part.Bodies.Count + 1):
        b = part.Bodies.Item(i)
        
        try:
            shape_count = b.Shapes.Count
            if shape_count == 0:
                continue
        except:
            continue
            
        try:
            ref = part.CreateReferenceFromObject(b)
            meas = spa.GetMeasurable(ref)
            
            # OOBB dummy array
            bbox_oobb = [0.0]*9
            meas.GetMinimumBoundingBox(bbox_oobb)
            
            d12 = math.sqrt((bbox_oobb[3]-bbox_oobb[0])**2 + (bbox_oobb[4]-bbox_oobb[1])**2 + (bbox_oobb[5]-bbox_oobb[2])**2)*1000
            d13 = math.sqrt((bbox_oobb[6]-bbox_oobb[0])**2 + (bbox_oobb[7]-bbox_oobb[1])**2 + (bbox_oobb[8]-bbox_oobb[2])**2)*1000
            
            print(f"[{i:3d}] {b.Name:30s} | {d12:.1f} x {d13:.1f}")
        except Exception as e:
            # print(f"[{i:3d}] FAILED: {e}")
            pass

test_oobb_all()
