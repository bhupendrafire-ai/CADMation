
import win32com.client
import pythoncom
import os
import time

def test_nuke_v3():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        target_doc = caa.Documents.Add("Part")
        target_part = target_doc.Part
        
        # Source doc is the active one
        source_doc = caa.ActiveDocument
        print(f"Source Doc: {source_doc.Name}")
        
        # Find a product to copy
        if "Product" in source_doc.Name:
            target_obj = source_doc.Product.Products.Item(1)
            print(f"Targeting Product: {target_obj.Name}")
        else:
            target_obj = source_doc.Part
            print(f"Targeting Part: {target_obj.Name}")
            
        # Standardized logic
        sel_source = source_doc.Selection
        sel_target = target_doc.Selection
        
        # Force activation
        source_doc.Activate()
        
        sel_source.Clear()
        sel_source.Add(target_obj)
        print(f"Selection count: {sel_source.Count}")
        
        sel_source.Copy()
        print("Copy success")
        
        target_doc.Activate()
        sel_target.Clear()
        sel_target.Add(target_part.MainBody)
        sel_target.PasteSpecial("AsResult")
        print("PasteSpecial success")
        
        target_part.Update()
        print(f"Shapes in transient part: {target_part.MainBody.Shapes.Count}")
        
        if target_part.MainBody.Shapes.Count > 0:
            temp_stl = os.path.join(os.environ['TEMP'], "test_nuke_v3.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            
            orig_alerts = caa.DisplayFileAlerts
            caa.DisplayFileAlerts = False
            try:
                target_doc.ExportData(temp_stl, "stl")
                print(f"Export Success: {os.path.getsize(temp_stl)} bytes")
            finally:
                caa.DisplayFileAlerts = orig_alerts
        else:
            print("FAILED: No shapes in transient part.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_nuke_v3()
