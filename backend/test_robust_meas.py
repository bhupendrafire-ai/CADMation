import win32com.client
import time

def test_robust_measurement():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        sel = active_doc.Selection
        
        # Get a part from the assembly
        prod = active_doc.Product
        if prod.Products.Count == 0:
            print("No children to test.")
            return
            
        child = prod.Products.Item(1)
        print(f"Testing on child: {child.Name}")
        
        try:
            ref_doc = child.ReferenceProduct.Parent
            part = ref_doc.Part
            body = part.MainBody
            print(f"  Target Body: {body.Name} in {ref_doc.Name}")
            
            # Method A: Local selection (likely to fail)
            print("\n  Method A: Local Selection")
            try:
                local_sel = ref_doc.Selection
                local_sel.Clear()
                local_sel.Add(body)
                show = local_sel.VisProperties.GetShow()
                print(f"    Local Selection Show: {show}")
            except Exception as e:
                print(f"    Local Selection Failed: {e}")
                
            # Method B: Global Selection (Likely to work)
            print("\n  Method B: Global Selection (ActiveDoc)")
            try:
                sel.Clear()
                sel.Add(body)
                show = sel.VisProperties.GetShow()
                print(f"    Global Selection Show: {show}")
                
                spa = active_doc.GetWorkbench("SPAWorkbench")
                measurable = spa.GetMeasurable(body)
                bbox = [0.0] * 6
                measurable.GetBoundaryBox(bbox)
                print(f"    Global SPA Success! Box: {bbox}")
            except Exception as e:
                print(f"    Global SPA Failed: {e}")
                
        except Exception as e:
            print(f"  Setup Failed: {e}")

    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_robust_measurement()
