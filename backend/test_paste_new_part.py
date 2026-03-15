import win32com.client
from app.services.catia_bridge import catia_bridge
import math

def test_paste_new_part():
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
    
    print("\nAttempting Paste Special technique into NEW document...")
    
    new_doc = None
    try:
        # 1. Create a selection in original part
        sel = part_doc.Selection
        sel.Clear()
        
        # 2. Add MainBody and copy
        sel.Add(part.MainBody)
        sel.Copy()
        sel.Clear()
        
        # 3. Create a new dummy Part document
        new_doc = caa.Documents.Add("Part")
        new_part = new_doc.Part
        
        # 4. Paste Special As Result
        new_sel = new_doc.Selection
        new_sel.Clear()
        new_sel.Add(new_part)
        new_sel.PasteSpecial("CATPrtResultWithOutLink")
        new_sel.Clear()
        
        new_part.Update()
        
        # 5. Measure the dummy body in NEW part
        spa = new_doc.GetWorkbench("SPAWorkbench")
        
        # We need to find the body that was just pasted
        num_bodies = new_part.Bodies.Count
        pasted_body = new_part.Bodies.Item(num_bodies)
        
        ref = new_part.CreateReferenceFromObject(pasted_body)
        m = spa.GetMeasurable(ref)
        
        try:
            b = [0.0]*6
            m.GetBoundaryBox(b)
            dx = abs(b[3]-b[0])*1000
            dy = abs(b[4]-b[1])*1000
            dz = abs(b[5]-b[2])*1000
            print(f"AABB [Isolated Solid]: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
        except Exception as box_e:
            print(f"AABB failed: {box_e}")
            
        try:
            oobb = [0.0]*9
            m.GetMinimumBoundingBox(oobb)
            d12 = math.sqrt((oobb[3]-oobb[0])**2 + (oobb[4]-oobb[1])**2 + (oobb[5]-oobb[2])**2)*1000
            d13 = math.sqrt((oobb[6]-oobb[0])**2 + (oobb[7]-oobb[1])**2 + (oobb[8]-oobb[2])**2)*1000
            print(f"OOBB Base Plane: {d12:.2f} x {d13:.2f} mm")
        except Exception as oe:
            # print(f"OOBB failed: {oe}")
            pass
            
    except Exception as e:
        print(f"Failed: {e}")
        
    finally:
        if new_doc:
            new_doc.Close()
        part_doc.Close()

test_paste_new_part()
