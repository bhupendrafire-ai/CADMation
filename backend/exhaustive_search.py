import win32com.client
import sys
import os

def exhaustive_search():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        print(f"Searching for AP_AXIS and 202_LOWER PLATE in {doc.Name}...")
        
        found_axis = []
        found_plate = []

        def walk(prod):
            # Check for AP_AXIS in this product's internal part
            try:
                ref = prod.ReferenceProduct
                if ref and hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                    part = ref.Parent.Part
                    for i in range(1, part.AxisSystems.Count + 1):
                        ax = part.AxisSystems.Item(i)
                        if "AP_AXIS" in ax.Name.upper():
                            print(f"FOUND AP_AXIS in {prod.Name} -> {ax.Name}")
                            found_axis.append((prod, ax))
            except: pass
            
            # Check for 202_LOWER PLATE
            if "202_LOWER PLATE" in prod.Name.upper() or "202_LOWER PLATE" in prod.PartNumber.upper():
                print(f"FOUND 202_LOWER PLATE: {prod.Name}")
                found_plate.append(prod)
            
            try:
                for i in range(1, prod.Products.Count + 1):
                    walk(prod.Products.Item(i))
            except: pass

        walk(doc.Product)
        
        if not found_axis:
            print("\nAP_AXIS NOT FOUND ANYWHERE.")
        if not found_plate:
            print("\n202_LOWER PLATE NOT FOUND ANYWHERE.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    exhaustive_search()
