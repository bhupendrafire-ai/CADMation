import win32com.client
import os
import sys

# Add the app directory to path to import services
sys.path.append(os.getcwd())

def test_master_stl():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        main_doc = caa.ActiveDocument
        target_name = "NE152000C001"
        def find_product(parent, name):
            for i in range(1, parent.Products.Count + 1):
                child = parent.Products.Item(i)
                if name.lower() in child.Name.lower() or name.lower() in child.PartNumber.lower(): return child
                res = find_product(child, name)
                if res: return res
            return None
        target = find_product(main_doc.Product, target_name)
        if not target: return print("Target not found")
        
        part_doc = target.ReferenceProduct.Parent
        print(f"Master Doc: {part_doc.Name}")
        
        # 1. Activate
        part_doc.Activate()
        
        # 2. STL Export (Active Window Context)
        temp_stl = "C:\\Temp\\master_test_stl.stl"
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        caa.DisplayFileAlerts = False
        try:
            part_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl):
                print(f"MASTER STL SUCCESS! Size: {os.path.getsize(temp_stl)}")
            else:
                print("MASTER STL FAILED to create file.")
        except Exception as e:
            print(f"MASTER STL Error: {e}")
        finally:
            caa.DisplayFileAlerts = True
            main_doc.Activate()

    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_master_stl()
