import win32com.client
from app.services.catia_bridge import catia_bridge

def check_props():
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
    
    print(f"Target: {target.Name}")
    try:
        props = target.ReferenceProduct.UserRefProperties
        print(f"User Properties Count: {props.Count}")
        for i in range(1, props.Count + 1):
            p = props.Item(i)
            print(f"  {p.Name} = {p.ValueAsString()}")
    except Exception as e:
        print(f"Error reading properties: {e}")

check_props()
