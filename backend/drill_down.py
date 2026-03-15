
import win32com.client
import pythoncom

def drill_down():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        target_doc = None
        sel = None
        
        # Search all documents for a selection
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            try:
                if doc.Selection.Count > 0:
                    target_doc = doc
                    sel = doc.Selection
                    break
            except: continue
        
        if target_doc and sel:
            print(f"Selection found in: {target_doc.Name}")
            raw_pop = sel.Item(1).Value
            print(f"Name: {getattr(raw_pop, 'Name', 'Unknown')}")
            
            # 1. Check if it's a Product with a Reference
            if hasattr(raw_pop, "ReferenceProduct"):
                ref = raw_pop.ReferenceProduct
                print(f"ReferenceProduct: {ref.Name} (Type: {type(ref).__name__})")
                
                # Check the Parent of the Reference (is it a Doc?)
                p = ref.Parent
                for _ in range(5):
                    print(f"  Parent: {getattr(p, 'Name', 'Unknown')} (Type: {type(p).__name__})")
                    if hasattr(p, "Part"):
                        print(f"  --- FOUND PART: {p.Part.Name}")
                    p = getattr(p, "Parent", None)
                    if not p: break
            
            # 2. Check for 'Part' attribute
            if hasattr(raw_pop, "Part"):
                print(f"Direct Part attribute: {raw_pop.Part.Name}")

            # 3. Check for 'MainBody'
            if hasattr(raw_pop, "MainBody"):
                print(f"Direct MainBody attribute: {raw_pop.MainBody.Name}")

            # 4. Check for 'Products' (is it a sub-product?)
            if hasattr(raw_pop, "Products"):
                print(f"Has {raw_pop.Products.Count} sub-products.")

        else:
            print("No selection found.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    drill_down()
