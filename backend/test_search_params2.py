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
    
    out_file = "params_matches.txt"
    with open(out_file, "w") as f:
        f.write("Searching Parameters inside 001_LOWER SHOE...\n")
        
        count = part.Parameters.Count
        for i in range(1, count + 1):
            try:
                p = part.Parameters.Item(i)
                val = p.ValueAsString()
                n = p.Name.upper()
                if any(x in val for x in ["1090", "910", "264"]) or any(x in n for x in ["STOCK", "BBOX", "SIZE", "OVERALL"]):
                    f.write(f"{p.Name} = {val}\n")
            except: pass

search_params()
