import win32com.client
import time

def test_selection_bbox():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        target = doc.Product

        print(f"Testing Selection-based measurement on: {target.Name}")
        
        try:
            sel.Clear()
            sel.Add(target)
            spa = doc.GetWorkbench("SPAWorkbench")
            # In CATIA, Measurable often works on the Selection Item
            measurable = spa.GetMeasurable(sel.Item(1).Value)
            bbox = [0.0] * 6
            measurable.GetBoundaryBox(bbox)
            print(f"Selection SPA Success! Box: {bbox}")
        except Exception as e:
            print(f"Selection SPA Failed: {e}")

        # Try ReferenceProduct
        try:
            print("\nTrying ReferenceProduct approach...")
            ref = target.ReferenceProduct
            measurable = spa.GetMeasurable(ref)
            bbox = [0.0] * 6
            measurable.GetBoundaryBox(bbox)
            print(f"ReferenceProduct SPA Success! Box: {bbox}")
        except Exception as e:
            print(f"ReferenceProduct SPA Failed: {e}")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_selection_bbox()
