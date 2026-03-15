import win32com.client
from app.services.catia_bridge import catia_bridge

def check_body_contents():
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
    part_doc = caa.Documents.Open(part_path)
    part = part_doc.Part
    
    print(f"\nMainBody: {part.MainBody.Name}")
    try:
        print(f"  Shapes count: {part.MainBody.Shapes.Count}")
    except:
        print("  Shapes count: ERROR")
        
    print("\nAll Bodies:")
    for i in range(1, part.Bodies.Count + 1):
        b = part.Bodies.Item(i)
        try:
            shape_count = b.Shapes.Count
            if shape_count > 0:
                print(f"[{i:3d}] {b.Name:30s} | Shapes: {shape_count}")
        except:
            pass
            
    part_doc.Close()

check_body_contents()
