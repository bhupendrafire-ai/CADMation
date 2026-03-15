
import win32com.client
import pythoncom

def list_children():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        target_doc = None
        sel = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            try:
                if doc.Selection.Count > 0:
                    target_doc = doc
                    sel = doc.Selection
                    break
            except: continue
        
        if target_doc and sel:
            root = sel.Item(1).Value
            print(f"Inspecting: {getattr(root, 'Name', 'Unknown')} ({type(root).__name__})")
            
            def dump_children(obj, depth=1):
                if hasattr(obj, "Products"):
                    for i in range(1, obj.Products.Count + 1):
                        child = obj.Products.Item(i)
                        print("  " * depth + f"- Child {i}: {child.Name} (PartNumber: {child.PartNumber})")
                        dump_children(child, depth + 1)
                
            dump_children(root)
            
            # Check for Part interface on Root
            try:
                if hasattr(root, "ReferenceProduct"):
                    ref = root.ReferenceProduct
                    print(f"Reference: {ref.Name}")
                    if hasattr(ref.Parent, "Part"):
                        print(f"Parent has Part: {ref.Parent.Part.Name}")
            except: pass

        else:
            print("No selection.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_children()
