import sys, os, time
import win32com.client
import pythoncom

def survey_bodies():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        print(f"Document: {doc.Name}")
        
        target = doc
        if hasattr(doc, "Product"):
            # If product, get the first instance's part for testing
            if doc.Product.Products.Count > 0:
                target = doc.Product.Products.Item(1)
        
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
            print("No Bodies collection found.")
            return

        print(f"Total Bodies in {test_obj.Parent.Name}: {test_obj.Bodies.Count}")
        
        # Check visibility and parentage for the first 50
        sel = doc.Selection
        for i in range(1, min(test_obj.Bodies.Count + 1, 150)):
            body = test_obj.Bodies.Item(i)
            
            # Check visibility via Selection
            sel.Clear()
            sel.Add(body)
            vis = "Unknown"
            try:
                vis_state = sel.VisProperties.GetShow() # 0 = Shown, 1 = Hidden
                vis = "Visible" if vis_state == 0 else "Hidden"
            except: pass
            
            print(f"[{i}] Name: {body.Name} | {vis}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    survey_bodies()
