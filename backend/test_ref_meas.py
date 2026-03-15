import win32com.client
import time

def test_reference_meas():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        
        # Find a Part document
        part_doc = None
        if ".CATPart" in active_doc.Name:
            part_doc = active_doc
        else:
            # Look for first part in assembly
            def find_part_doc(prod):
                try:
                    ref_doc = prod.ReferenceProduct.Parent
                    if ".CATPart" in ref_doc.Name: return ref_doc
                except: pass
                for i in range(1, prod.Products.Count + 1):
                    res = find_part_doc(prod.Products.Item(i))
                    if res: return res
                return None
            part_doc = find_part_doc(active_doc.Product)
            
        if not part_doc:
            print("No Part document found to test.")
            return
            
        print(f"Testing on Part: {part_doc.Name}")
        part = part_doc.Part
        body = part.MainBody
        
        spa = part_doc.GetWorkbench("SPAWorkbench")
        
        # Try 1: Direct object
        print("\n  Try 1: Direct MainBody")
        try:
            m = spa.GetMeasurable(body)
            b = [0.0]*6
            m.GetBoundaryBox(b)
            print(f"    Success! Box: {b}")
        except Exception as e:
            print(f"    Failed: {e}")
            
        # Try 2: Reference
        print("\n  Try 2: CreateReferenceFromObject(MainBody)")
        try:
            ref = part.CreateReferenceFromObject(body)
            m = spa.GetMeasurable(ref)
            b = [0.0]*6
            m.GetBoundaryBox(b)
            print(f"    Success! Box: {b}")
        except Exception as e:
            print(f"    Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_reference_meas()
