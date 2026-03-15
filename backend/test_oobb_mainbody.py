import win32com.client
from app.services.catia_bridge import catia_bridge
import math

def test_oobb_mainbody():
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
        
        b = [0.0]*9
        m.GetMinimumBoundingBox(b)
        
        d12 = math.sqrt((b[3]-b[0])**2 + (b[4]-b[1])**2 + (b[5]-b[2])**2)*1000
        d13 = math.sqrt((b[6]-b[0])**2 + (b[7]-b[1])**2 + (b[8]-b[2])**2)*1000
        
        try:
            vol = m.Volume * 1e9
            d3 = vol / (d12 * d13) if (d12 > 0 and d13 > 0) else 0
        except Exception as e:
            # If Volume fails, just print the base area dimensions
            d3 = 0
            
        dims = sorted([d12, d13, d3], reverse=True)
        print(f"OOBB dimensions: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f}")
        
    except Exception as e:
        print(f"Failed: {e}")

test_oobb_mainbody()
