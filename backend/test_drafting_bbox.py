import win32com.client
from app.services.catia_bridge import catia_bridge

def test_drawing_bbox():
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
    
    print("\nAttempting Generating Drafting technique...")
    
    try:
        # Create a new drawing
        draw_doc = caa.Documents.Add("Drawing")
        sheet = draw_doc.DrawingRoot.ActiveSheet
        
        # We need the 3D document object to pass to GenerativeBehavior
        part_doc = caa.Documents.Item(ref_doc.Name)
        
        # 1. Front View (XY plane equivalent)
        front_view = sheet.Views.Add("FrontView")
        gen_behavior_front = front_view.GenerativeBehavior
        gen_behavior_front.Document = part_doc.Product
        gen_behavior_front.DefineFrontView(0, 1, 0, 0, 0, 1) # Looking at XZ plane
        
        # 2. Top View
        top_view = sheet.Views.Add("TopView")
        gen_behavior_top = top_view.GenerativeBehavior
        gen_behavior_top.Document = part_doc.Product
        gen_behavior_top.DefineFrontView(0, 0, 1, 1, 0, 0) # Looking at XY plane
        
        # 3. Side View
        side_view = sheet.Views.Add("SideView")
        gen_behavior_side = side_view.GenerativeBehavior
        gen_behavior_side.Document = part_doc.Product
        gen_behavior_side.DefineFrontView(1, 0, 0, 0, 1, 0) # Looking at YZ plane
        
        # Update views
        print("Updating drafting views...")
        gen_behavior_front.Update()
        gen_behavior_top.Update()
        gen_behavior_side.Update()
        
        print("Views generated. Extracting bounds...")
        
        # Try to get 2D bounding box
        # View object doesn't have a direct "Size" normally, but we can get it via Size() method which returns a tuple
        coords_f = [0.0]*4
        front_view.Size(coords_f)
        w_f = abs(coords_f[2] - coords_f[0])
        h_f = abs(coords_f[3] - coords_f[1])
        print(f"Front View Size: {w_f:.1f} x {h_f:.1f}")
        
        coords_t = [0.0]*4
        top_view.Size(coords_t)
        w_t = abs(coords_t[2] - coords_t[0])
        h_t = abs(coords_t[3] - coords_t[1])
        print(f"Top View Size: {w_t:.1f} x {h_t:.1f}")
        
        coords_s = [0.0]*4
        side_view.Size(coords_s)
        w_s = abs(coords_s[2] - coords_s[0])
        h_s = abs(coords_s[3] - coords_s[1])
        print(f"Side View Size: {w_s:.1f} x {h_s:.1f}")
        
        draw_doc.Close()
        print("Closed drawing.")
        
    except Exception as e:
        print(f"Failed drafting bounds: {e}")

test_drawing_bbox()
