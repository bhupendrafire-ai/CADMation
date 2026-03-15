import win32com.client
import os
import sys

# Add the app directory to path to import services
sys.path.append(os.getcwd())

def verify_target_size():
    try:
        from app.services.geometry_service import geometry_service
        caa = win32com.client.GetActiveObject("CATIA.Application")
        main_doc = caa.ActiveDocument
        
        # User specified NE1520000C001 (noted the extra 0, checking for both)
        possible_names = ["NE1520000C001", "NE152000C001"]
        
        def find_product(parent, names):
            for i in range(1, parent.Products.Count + 1):
                child = parent.Products.Item(i)
                if any(n.lower() in child.Name.lower() or n.lower() in child.PartNumber.lower() for n in names):
                    return child
                res = find_product(child, names)
                if res: return res
            return None
            
        target = find_product(main_doc.Product, possible_names)
        if not target:
            print(f"Target {possible_names} not found. Please ensure the part is visible in the tree.")
            return

        print(f"Target Resolved: {target.Name} (PN: {target.PartNumber})")
        
        # ACTUALLY CALL THE PRODUCTION SERVICE
        result = geometry_service.get_bounding_box(target)
        print(f"FINAL_RESULT: {result}")

    except Exception as e:
        print(f"Verification Failed: {e}")

if __name__ == "__main__":
    verify_target_size()
