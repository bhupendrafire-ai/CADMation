
import win32com.client
import pythoncom
import os
import time

def test_component_copy():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # 1. Target the selection (User has it selected!)
        parent_doc = caa.ActiveDocument
        selection = parent_doc.Selection
        
        target_prod = None
        if selection.Count > 0:
            target_prod = selection.Item(1).Value
            print(f"Using Current Selection: {target_prod.Name}")
        else:
            # Search by name in active doc
            print("No selection. Searching for 'LOWER_STEEL' in active assembly...")
            main_prod = parent_doc.Product
            for i in range(1, main_prod.Products.Count + 1):
                p = main_prod.Products.Item(i)
                if "lower_steel" in p.Name.lower():
                    target_prod = p
                    break
        
        if not target_prod:
            print("FAILED: Target component not found.")
            return

        # 2. THE EXTRACTION
        print(f"Extracting Component: {target_prod.Name}")
        selection.Clear()
        selection.Add(target_prod)
        try:
            selection.Copy()
            print("  Copy SUCCESS.")
        except Exception as e:
            print(f"  Copy FAILED: {e}")
            return

        # 3. PASTE TO NEW PART
        transit_doc = caa.Documents.Add("Part")
        transit_part = transit_doc.Part
        sel_target = transit_doc.Selection
        sel_target.Add(transit_part)
        try:
            sel_target.PasteSpecial("AsResult")
            transit_part.Update()
            print("  Paste SUCCESS.")
            
            # 4. EXPORT
            temp_stl = os.path.join(os.environ["TEMP"], "nuke_component_final.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            transit_doc.ExportData(temp_stl, "stl")
            print(f"!!! SUCCESS !!! STL generated: {os.path.getsize(temp_stl)} bytes")
            
        except Exception as e:
            print(f"  Paste/Export Failed: {e}")
        
        transit_doc.Close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_component_copy()
