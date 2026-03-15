import win32com.client
import os

def test_inertia_tech_object():
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
        
        # Method 1 from User: part.GetTechnologicalObject("Inertia")
        try:
            part = target.GetItem("Part")
            if not part:
                part = target.ReferenceProduct.Parent.Part
            
            print(f"Part: {part.Name}")
            # Try GetTechnologicalObject on Part
            try:
                 inertia = part.GetTechnologicalObject("Inertia")
                 bbox = [0.0]*13 # Some docs say Inertia needs 13
                 try:
                     inertia.GetBoundingBox(bbox)
                     print(f"Inertia Tech Object BBox: {bbox[:6]}")
                 except Exception as e:
                     print(f"Inertia Tech Object GetBoundingBox Failed: {e}")
            except Exception as e:
                 print(f"GetTechnologicalObject('Inertia') Failed: {e}")
                 
        except Exception as e:
            print(f"Part resolution failed: {e}")

    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_inertia_tech_object()
