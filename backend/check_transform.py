import win32com.client
import sys

def check_transform():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        def find_product(prod, name):
            if name.upper() in prod.Name.upper() or name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_product(prod.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        target = find_product(doc.Product, "202_LOWER PLATE")
        if not target: return
        
        print(f"Target: {target.Name}")
        matrix = [0.0] * 12
        target.GetPosition(matrix)
        print(f"Transformation Matrix: {matrix}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_transform()
