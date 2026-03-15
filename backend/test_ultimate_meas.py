import win32com.client
import time

def test_ultimate_meas():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        
        # We need a part from the assembly
        def find_any_part(prod):
            try:
                ref_doc = prod.ReferenceProduct.Parent
                if ".CATPart" in ref_doc.Name: return (prod, ref_doc.Part)
            except: pass
            for i in range(1, prod.Products.Count + 1):
                res = find_any_part(prod.Products.Item(i))
                if res: return res
            return (None, None)

        prod_inst, part_obj = find_any_part(active_doc.Product)
        if not prod_inst:
            print("No part found.")
            return

        print(f"Testing on {prod_inst.Name} / {part_obj.Parent.Name}")
        
        # SPA from active doc
        spa = active_doc.GetWorkbench("SPAWorkbench")
        
        # Test 1: Measure the Product Instance (often works for products in assemblies)
        print("\nTest 1: SPA.GetMeasurable(ProductInstance)")
        try:
            m = spa.GetMeasurable(prod_inst)
            b = [0.0]*6
            m.GetBoundaryBox(b)
            print(f"  Success: {b}")
        except Exception as e:
            print(f"  Failed: {e}")

        # Test 2: Measure Reference of Product Instance
        print("\nTest 2: SPA.GetMeasurable(ProductInstance.ReferenceProduct)")
        try:
            m = spa.GetMeasurable(prod_inst.ReferenceProduct)
            b = [0.0]*6
            m.GetBoundaryBox(b)
            print(f"  Success: {b}")
        except Exception as e:
            print(f"  Failed: {e}")

        # Test 3: Measure MainBody with local reference
        print("\nTest 3: Part.CreateReferenceFromObject(MainBody)")
        try:
            ref = part_obj.CreateReferenceFromObject(part_obj.MainBody)
            m = spa.GetMeasurable(ref) # Try with global spa
            b = [0.0]*6
            m.GetBoundaryBox(b)
            print(f"  Success: {b}")
        except Exception as e:
            print(f"  Failed: {e}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ultimate_meas()
