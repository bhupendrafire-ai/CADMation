import win32com.client
import os
import traceback

def test_user_methods():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        target_name = "NE152000C001"
        
        def find_product(parent, name):
            for i in range(1, parent.Products.Count + 1):
                child = parent.Products.Item(i)
                if name.lower() in child.Name.lower() or name.lower() in child.PartNumber.lower():
                    return child
                res = find_product(child, name)
                if res: return res
            return None
            
        target = find_product(doc.Product, target_name)
        if not target:
            print("Target not found")
            return
            
        print(f"Target Resolved: {target.Name}")
        
        # Resolve Part
        part = None
        try:
            part = target.GetItem("Part")
            if part: print("Found Part via GetItem")
        except: pass
        
        if not part:
            try:
                part = target.ReferenceProduct.Parent.Part
                if part: print("Found Part via ReferenceProduct.Parent.Part")
            except: pass
            
        if not part:
             print("Could not resolve Part object.")
             return

        # METHOD 1: part.GetTechnologicalObject("Inertia")
        print("\n--- Method 1: GetTechnologicalObject('Inertia') ---")
        try:
             inertia = part.GetTechnologicalObject("Inertia")
             bbox = [0.0]*13
             inertia.GetBoundingBox(bbox)
             print(f" Success! BBox: {bbox[:6]}")
        except Exception as e:
             print(f" Failed: {e}")

        # METHOD 2: SPA (Standard, I've tried this, but let's try exactly as suggested)
        print("\n--- Method 2: SPA Measurable from Reference ---")
        try:
             spa = doc.GetWorkbench("SPAWorkbench")
             ref = part.CreateReferenceFromObject(part.MainBody)
             m = spa.GetMeasurable(ref)
             bbox = [0.0]*6
             m.GetBoundaryBox(bbox)
             print(f" Success! BBox: {bbox}")
        except Exception as e:
             print(f" Failed: {e}")

        # METHOD 3: STL (Check if ExportData even works for this part)
        print("\n--- Method 3: STL Export Check ---")
        try:
             temp_stl = "C:\\Temp\\debug_test.stl"
             if not os.path.exists("C:\\Temp"): os.makedirs("C:\\Temp")
             if os.path.exists(temp_stl): os.remove(temp_stl)
             
             # The export usually works on the Document containing the part
             p_doc = part.Parent
             print(f" Exporting Document: {p_doc.Name}")
             p_doc.ExportData(temp_stl, "stl")
             
             if os.path.exists(temp_stl):
                  size = os.path.getsize(temp_stl)
                  print(f" Success! STL Size: {size} bytes")
             else:
                  print(" Failed: STL file not created.")
        except Exception as e:
             print(f" Failed: {e}")

    except Exception as e:
        print(f"Overall Test Failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_user_methods()
