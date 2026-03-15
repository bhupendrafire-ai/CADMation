import win32com.client
from app.services.catia_bridge import catia_bridge
import time

def dump_params():
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
    
    with open("all_params.txt", "w", encoding="utf-8") as f:
        count = part.Parameters.Count
        f.write(f"Total Params: {count}\n")
        
        for i in range(1, count + 1):
            try:
                p = part.Parameters.Item(i)
                f.write(f"{p.Name} = {p.ValueAsString()}\n")
            except Exception as e:
                f.write(f"Failed param {i}: {e}\n")

dump_params()
