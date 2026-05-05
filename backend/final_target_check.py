import win32com.client
import sys
import os

def final_check():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        target_name = "202_LOWER PLATE"
        print(f"Searching for: {target_name}")
        
        def find_obj(prod):
            if target_name.upper() in prod.Name.upper() or target_name.upper() in prod.PartNumber.upper():
                return prod
            try:
                # Add child names to debug if not found
                for i in range(1, prod.Products.Count + 1):
                    res = find_obj(prod.Products.Item(i))
                    if res: return res
            except: pass
            return None

        target = find_obj(doc.Product)
        if target:
            print(f"FOUND: {target.Name} (PartNumber: {target.PartNumber})")
        else:
            print("NOT FOUND")
            
            # List some likely candidates
            print("Checking top-level names:")
            for i in range(1, doc.Product.Products.Count + 1):
                p = doc.Product.Products.Item(i)
                if "LOWER" in p.Name.upper() or "PLATE" in p.Name.upper():
                    print(f"Candidate: {p.Name}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    final_check()
