import sys, os, time
import win32com.client
import pythoncom

def test_parent_logic():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        
        target = doc
        if hasattr(doc, "Product") and doc.Product.Products.Count > 0:
            target = doc.Product.Products.Item(1)

        test_obj = target
        if hasattr(test_obj, "ReferenceProduct"):
            try:
                ref = test_obj.ReferenceProduct
                if hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                    test_obj = ref.Parent.Part
            except: pass
        if hasattr(test_obj, "Part"): test_obj = test_obj.Part
        
        if not hasattr(test_obj, "Bodies"):
            print("No Bodies.")
            return

        bodies_coll_name = test_obj.Bodies.Name
        print(f"Bodies Collection Name: {bodies_coll_name}")

        root_count = 0
        for i in range(1, test_obj.Bodies.Count + 1):
            b = test_obj.Bodies.Item(i)
            p = b.Parent
            p_name = "Unknown"
            p_type = "Unknown"
            try:
                p_name = p.Name
                p_type = type(p).__name__
            except: pass
            
            # Check if parent IS the Bodies collection of this part
            is_root = False
            # If the parent's parent is the Part, and parent's name is 'Bodies', it's likely a root
            try:
                if p_name == bodies_coll_name and "Bodies" in p_type:
                    is_root = True
            except: pass

            if is_root or i < 20: # Show first 20 even if not root for context
                print(f"[{i}] {b.Name} | Parent: {p_name} ({p_type}) | ROOT: {is_root}")
                if is_root: root_count += 1

        print(f"\nFinal Root Count: {root_count}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_parent_logic()
