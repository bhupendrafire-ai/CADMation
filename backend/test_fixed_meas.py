import win32com.client
import time

def test_fixed_measurement():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        
        # Find any Part in assembly
        def find_part(prod):
            try:
                ref_doc = prod.ReferenceProduct.Parent
                if ".CATPart" in ref_doc.Name: return (prod, ref_doc)
            except: pass
            for i in range(1, prod.Products.Count + 1):
                res = find_part(prod.Products.Item(i))
                if res: return res
            return (None, None)

        prod_inst, part_doc = find_part(active_doc.Product)
        if not prod_inst:
            print("No part found.")
            return

        print(f"Testing on: {prod_inst.Name}")
        
        # KEY: We must get the SPAWorkbench from the PART document, 
        # but we might need to use its Selection to "see" the reference.
        try:
            part = part_doc.Part
            body = part.MainBody
            
            # Create a reference via the product instance (Assembly Reference)
            # This is the "Magic" for assembly measurement
            print("\n  Test: Measure via Product.GetItem('PartConnector')")
            # In CATIA, you can sometimes get a measurable directly from the product
            try:
                m = prod_inst.GetItem("Measurable")
                b = [0.0]*6
                m.GetBoundaryBox(b)
                print(f"    Success! Box: {b}")
            except Exception as e:
                print(f"    GetItem('Measurable') failed: {e}")

            print("\n  Test: Measure via Assembly Selection Reference")
            sel = active_doc.Selection
            sel.Clear()
            sel.Add(prod_inst)
            try:
                # This works if the product corresponds to the part
                ref = sel.Item(1).Reference
                spa = active_doc.GetWorkbench("SPAWorkbench")
                m = spa.GetMeasurable(ref)
                b = [0.0]*6
                m.GetBoundaryBox(b)
                print(f"    Success! Box: {b}")
            except Exception as e:
                 print(f"    Selection Reference failed: {e}")

        except Exception as e:
            print(f"  Test Logic Error: {e}")

    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    test_fixed_measurement()
