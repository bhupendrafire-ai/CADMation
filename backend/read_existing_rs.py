import win32com.client
import sys

def read_rough_stock():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        print("Searching for existing Rough stock.1 feature...")
        sel.Clear()
        sel.Search("Name='*Rough stock.1*',all")
        
        if sel.Count == 0:
            print("Existing 'Rough stock.1' not found in this document context.")
            # Search globally in children
            def find_rs(prod):
                try:
                    ref = prod.ReferenceProduct
                    part = ref.Parent.Part
                    for i in range(1, part.HybridBodies.Count + 1):
                        hb = part.HybridBodies.Item(i)
                        for j in range(1, hb.HybridShapes.Count + 1):
                            hs = hb.HybridShapes.Item(j)
                            if "ROUGH STOCK" in hs.Name.upper(): return hs
                except: pass
                try:
                    for i in range(1, prod.Products.Count + 1):
                        r = find_rs(prod.Products.Item(i))
                        if r: return r
                except: pass
                return None
            
            rs_feat = find_rs(doc.Product)
            if rs_feat:
                print(f"Found existing Rough Stock: {rs_feat.Name}")
            else:
                print("Could not find any Rough Stock feature.")
                return
        else:
            rs_feat = sel.Item(1).Value
            print(f"Found existing Rough Stock: {rs_feat.Name}")

        # Try to read parameters or name
        # Some Rough Stock features encode dimensions in their name or parameters
        print(f"Feature Name: {rs_feat.Name}")
        
        # Check parent part parameters
        try:
            parent_part = rs_feat.Parent.Parent
            if hasattr(parent_part, "Parameters"):
                print("Checking parameters close to feature...")
                for i in range(1, parent_part.Parameters.Count + 1):
                    p = parent_part.Parameters.Item(i)
                    if any(x in p.Name.upper() for x in ["DX", "DY", "DZ", "STOCK", "LENGTH", "WIDTH", "HEIGHT"]):
                         # Filter for ones that might be related to this RS
                        print(f"  Param: {p.Name} = {p.ValueAsString()}")
        exceptException: pass

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    read_rough_stock()
