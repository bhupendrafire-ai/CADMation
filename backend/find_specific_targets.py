import win32com.client
import sys
import os

def find_targets():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        print(f"Active Document: {doc.Name}")
        
        targets = ["INPUT PART_01", "202_LOWER PLATE"]
        found = {}

        def walk(prod):
            name = prod.Name.upper()
            pn = prod.PartNumber.upper()
            
            for t in targets:
                if t.upper() in name or t.upper() in pn:
                    print(f"Found Match: {prod.Name} (PartNumber: {prod.PartNumber})")
                    found[t] = prod
            
            # Check for AP_AXIS
            try:
                ref = prod.ReferenceProduct
                if ref and hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                    part = ref.Parent.Part
                    for i in range(1, part.AxisSystems.Count + 1):
                        ax = part.AxisSystems.Item(i)
                        if "AP_AXIS" in ax.Name.upper():
                            print(f"Found AP_AXIS in: {prod.Name} -> {ax.Name}")
            except: pass
            
            try:
                for i in range(1, prod.Products.Count + 1):
                    walk(prod.Products.Item(i))
            except: pass

        walk(doc.Product)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_targets()
