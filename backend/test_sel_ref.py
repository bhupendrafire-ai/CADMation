import win32com.client
import time

def test_sel_ref_meas():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        sel = active_doc.Selection
        
        # Get any part instance
        prod = active_doc.Product
        if prod.Products.Count == 0: return
        child = prod.Products.Item(1)
        print(f"Target: {child.Name}")
        
        sel.Clear()
        sel.Add(child)
        
        spa = active_doc.GetWorkbench("SPAWorkbench")
        
        # Method: Measurement on Selection Reference
        print("\nTest: SPA.GetMeasurable(Selection.Item(1).Reference)")
        try:
            # Note: Item(1).Reference is the key for assembly measurement
            ref = sel.Item(1).Reference
            m = spa.GetMeasurable(ref)
            b = [0.0]*6
            m.GetBoundaryBox(b)
            print(f"  Success! Box: {b}")
            dx = abs(b[3]-b[0])*1000
            dy = abs(b[4]-b[1])*1000
            print(f"  Dims: {dx:.1f} x {dy:.1f}")
        except Exception as e:
            print(f"  Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_sel_ref_meas()
