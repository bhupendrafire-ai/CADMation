
import win32com.client
import pythoncom
import os
import time

def verify_fixes():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        initial_doc_name = caa.ActiveDocument.Name
        print(f"Initial Active Document: {initial_doc_name}")
        
        # We'll test on the first product child if it's an assembly, or the part itself
        doc = caa.ActiveDocument
        target_obj = None
        
        if ".CATProduct" in doc.Name:
            def find_leaf(p):
                print(f"  Checking {p.Name} (Children: {p.Products.Count})")
                if p.Products.Count == 0: return p
                for i in range(1, p.Products.Count + 1):
                    res = find_leaf(p.Products.Item(i))
                    if res: return res
                return None
            
            target_obj = find_leaf(doc.Product)
            if not target_obj:
                print("Could not find any part in the assembly.")
                return
        else:
            target_obj = doc.Part
            
        print(f"Final Target Object: {target_obj.Name}")
        
        # Import the service directly to test its logic
        import sys
        sys.path.append(r"H:\CADMation\backend")
        from app.services.geometry_service import geometry_service
        
        print("\nStep 1: Testing Bounding Box Measurement...")
        start_time = time.time()
        bbox = geometry_service.get_bounding_box(target_obj)
        end_time = time.time()
        
        print(f"Result: {bbox.get('stock_size')}")
        print(f"Time taken: {end_time - start_time:.2f}s")
        
        print("\nStep 2: Checking for session corruption...")
        final_doc_name = caa.ActiveDocument.Name
        print(f"Final Active Document: {final_doc_name}")
        
        if "iso_" in final_doc_name:
            print("FAILED: Session corruption detected (iso_ filename).")
        elif final_doc_name != initial_doc_name:
            print(f"WARNING: Active document changed from {initial_doc_name} to {final_doc_name}")
        else:
            print("SUCCESS: Session preserved.")
            
        if bbox.get("stock_size") == "Not Measurable":
            print("FAILED: Measurement failed (Not Measurable).")
        else:
            print("SUCCESS: Measurement obtained.")

    except Exception as e:
        print(f"Verification Error: {e}")

if __name__ == "__main__":
    verify_fixes()
