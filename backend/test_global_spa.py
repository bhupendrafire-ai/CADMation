import win32com.client
import os

def test_global_spa():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        target_name = "NE152000C001"
        def find_product(parent, name):
            for i in range(1, parent.Products.Count + 1):
                child = parent.Products.Item(i)
                if name.lower() in child.Name.lower() or name.lower() in child.PartNumber.lower(): return child
                res = find_product(child, name)
                if res: return res
            return None
        target = find_product(doc.Product, target_name)
        if not target: return print("Target not found")
        
        # 1. Try Global Workbench
        print("Try Global SPAWorkbench...")
        try:
            spa = caa.GetWorkbench("SPAWorkbench")
            m = spa.GetMeasurable(target)
            bbox = [0.0]*6
            m.GetBoundaryBox(bbox)
            print(f"  GLOBAL SPA SUCCESS: {bbox}")
        except Exception as e:
            print(f"  GLOBAL SPA FAILED: {e}")

        # 2. Try the "Analyze" object's properties
        try:
            analyze = target.Analyze
            # In some versions, Analyze.GetBBox or BoundingBox works
            bbox = [0.0]*6
            # Try to see if it has a BoundingBox property
            try:
                bb = analyze.BoundingBox
                print(f"  Analyze.BoundingBox property: {bb}")
            except: pass
        except: pass

        # 3. Check for hidden geometry in "CGR" mode
        try:
            rep = target.GetItem("Rep")
            print(f"  Found Rep: {rep.Name}")
        except: pass

    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    test_global_spa()
