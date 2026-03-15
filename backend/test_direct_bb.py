
import win32com.client
import pythoncom
import os
import time

def test_direct_bb():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # 1. Target the component
        target_doc = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if "lower_steel" in doc.Name.lower():
                target_doc = doc
                break
        
        if not target_doc:
            print("FAILED: Document not found.")
            return

        print(f"Direct SPA Measurement for: {target_doc.Name}")
        
        # 2. Setup SPA
        try:
            the_spa = caa.ActiveDocument.GetWorkbench("SPAWorkbench")
            print("  SPA Workbench Access SUCCESS.")
        except Exception as e:
            print(f"  SPA Workbench Access FAILED: {e}")
            return

        # 3. Targeted Measurement
        # We try to measure the Document's Product (most robust for Assemblies)
        prod = target_doc.Product
        try:
            measurable = the_spa.GetMeasurable(prod)
            print("  Measurable Interface SUCCESS.")
            
            # Get Bounding Box
            # format: (oMinX, oMaxX, oMinY, oMaxY, oMinZ, oMaxZ)
            bb = [0.0] * 6
            bb = measurable.GetBoundingBox(bb) # Some versions return it, some fill the list
            
            # Workaround for different types of COM returns
            if isinstance(bb, tuple) or isinstance(bb, list):
                print(f"  !!! SUCCESS !!! Bounding Box: {bb}")
                width = abs(bb[1] - bb[0])
                length = abs(bb[3] - bb[2])
                height = abs(bb[5] - bb[4])
                print(f"  Dimensions: {width:.2f} x {length:.2f} x {height:.2f}")
            else:
                print(f"  BB call returned unexpected type: {type(bb)}. Value: {bb}")
                
        except Exception as e:
            print(f"  Measurement Logic Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_direct_bb()
