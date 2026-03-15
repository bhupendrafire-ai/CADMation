import win32com.client
import os
import sys

# Add the app directory to path to import services
sys.path.append(os.getcwd())

def test_selection_load():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        main_doc = caa.ActiveDocument
        
        target_name = "NE152000C001"
        def find_product(parent, name):
            for i in range(1, parent.Products.Count + 1):
                child = parent.Products.Item(i)
                if name.lower() in child.Name.lower() or name.lower() in child.PartNumber.lower(): return child
                res = find_product(child, name)
                if res: return res
            return None
            
        target = find_product(main_doc.Product, target_name)
        if not target: return print("Target not found")
        
        print(f"Target: {target.Name}")
        
        # 1. Force Selection (Heavy Duty Load)
        sel = main_doc.Selection
        sel.Clear()
        sel.Add(target)
        print("Target added to selection.")
        
        # 2. Try Measurable
        spa = main_doc.GetWorkbench("SPAWorkbench")
        try:
            m = spa.GetMeasurable(target)
            bbox = [0.0]*6
            m.GetBoundaryBox(bbox)
            print(f"Measurable with Selection Result: {bbox}")
        except Exception as e:
            print(f"Measurable still failing: {e}")

        # 3. Try Inertia
        try:
            inertia = spa.GetInertia(target)
            bbox = [0.0]*6
            inertia.GetBoundingBox(bbox)
            print(f"Inertia with Selection Result: {bbox}")
        except Exception as e:
            print(f"Inertia still failing: {e}")

    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_selection_load()
