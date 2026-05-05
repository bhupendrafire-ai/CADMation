import win32com.client
import sys
import os

def list_structure():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        print(f"Active Document: {doc.Name}")
        
        def walk(prod, depth=0):
            indent = "  " * depth
            print(f"{indent}- {prod.Name} (PartNumber: {prod.PartNumber})")
            
            # Check for AP_AXIS in this product's Part (if it is one)
            try:
                ref = prod.ReferenceProduct
                if ref and hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                    part = ref.Parent.Part
                    for i in range(1, part.AxisSystems.Count + 1):
                        ax = part.AxisSystems.Item(i)
                        print(f"{indent}  [AXIS] {ax.Name}")
            except: pass
            
            try:
                for i in range(1, prod.Products.Count + 1):
                    walk(prod.Products.Item(i), depth + 1)
            except: pass

        walk(doc.Product)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_structure()
