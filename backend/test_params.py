import win32com.client
from app.services.catia_bridge import catia_bridge

def inspect_params():
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
    
    print(f"Found: {target.Name}")
    try:
        ref_doc = target.ReferenceProduct.Parent
        part = ref_doc.Part
        
        print(f"Parameters Count: {part.Parameters.Count}")
        for i in range(1, part.Parameters.Count + 1):
            p = part.Parameters.Item(i)
            print(f"  {p.Name} = {p.ValueAsString()}")
            
    except Exception as e:
        print(f"Error: {e}")

inspect_params()
