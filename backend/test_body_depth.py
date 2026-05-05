import sys, os, time
import win32com.client
import pythoncom

def test_depth():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        
        target = doc
        if hasattr(doc, "Product") and doc.Product.Products.Count > 0:
            target = doc.Product.Products.Item(1)
            print(f"Targeting Instance: {target.Name}")

        # Drill to Part
        test_obj = target
        if hasattr(test_obj, "ReferenceProduct"):
            try:
                ref = test_obj.ReferenceProduct
                if hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                    test_obj = ref.Parent.Part
            except: pass
        if hasattr(test_obj, "Part"): test_obj = test_obj.Part
        
        if not hasattr(test_obj, "Bodies"):
            print("No Bodies collection.")
            return

        print(f"Total Bodies in collection: {test_obj.Bodies.Count}")
        
        # We want to see if we can find 'Immediate' children of the Part
        # Or if we can check the 'Parent' of the body.
        for i in range(1, min(test_obj.Bodies.Count + 1, 50)):
            b = test_obj.Bodies.Item(i)
            parent = "None"
            try:
                parent = b.Parent.Name
            except: pass
            
            # Check if it's the 'MainBody'
            is_main = "No"
            try:
                if b.Name == test_obj.MainBody.Name:
                    is_main = "YES (MainBody)"
            except: pass

            print(f"[{i}] {b.Name} | Parent: {parent} | Main: {is_main}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_depth()
