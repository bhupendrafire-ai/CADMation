
import win32com.client
import pythoncom
import os
import time

def test_inertia_bb():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        target_doc = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if "lower_steel" in doc.Name.lower():
                target_doc = doc
                break
        
        if not target_doc:
            print("FAILED: Document not found.")
            return

        print(f"Inertia Measurement for: {target_doc.Name}")
        
        # 1. GET PRODUCT
        prod = target_doc.Product
        
        # 2. GET INERTIA
        try:
            # Inertia is a technological object
            inertia = prod.GetTechnologicalObject("Inertia")
            print("  Inertia Object Access SUCCESS.")
            
            # 3. GET BOUNDING BOX
            # The method fills an array of 6 doubles
            # Format in Python win32com often requires a specific syntax
            # oComponents = (minx, maxx, miny, maxy, minz, maxz)
            
            try:
                # Some versions return the tuple, some need it passed
                bb = inertia.GetBoundingBox()
                print(f"  !!! SUCCESS !!! Bounding Box: {bb}")
                
                # If width/etc are available directly
                # inertia.Mass, inertia.Volume also highly useful
                print(f"  Mass: {inertia.Mass:.3f} kg, Volume: {inertia.Volume:.3f} m3")
                
            except Exception as e:
                print(f"  GetBoundingBox failed: {e}. Trying direct properties if exist...")
                # Fallback: maybe we can get dimensions another way
                
        except Exception as e:
            print(f"  Inertia Access Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_inertia_bb()
