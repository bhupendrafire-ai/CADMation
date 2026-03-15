import win32com.client
from app.services.catia_bridge import catia_bridge

def search_params():
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
    
    print("Searching Parameters inside 001_LOWER SHOE...")
    for i in range(1, part.Parameters.Count + 1):
        p = part.Parameters.Item(i)
        try:
            val = p.ValueAsString()
            # If it's a known dimension
            if any(x in val for x in ["1090", "910", "264"]) or any(x in p.Name.upper() for x in ["STOCK", "LENGTH", "WIDTH", "HEIGHT", "SIZE", "BBOX"]):
                print(f"{p.Name} = {val}")
        except: pass

search_params()
