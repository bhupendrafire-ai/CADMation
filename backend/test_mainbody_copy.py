
import win32com.client
import pythoncom
import os
import time

def test_mainbody_copy():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        target_doc = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if "lower_steel" in doc.Name.lower():
                target_doc = doc
                break
        
        if not target_doc:
            print("FAILED: Could not find LOWER_STEEL document.")
            return

        print(f"MainBody Targeting for: {target_doc.Name}")
        target_doc.Activate()
        part = target_doc.Part
        
        # 1. ACCESS MAINBODY
        main_body = None
        try:
            main_body = part.MainBody
            print(f"  MainBody Access SUCCESS: {main_body.Name}")
        except Exception as e:
            print(f"  MainBody Access FAILED: {e}")
            return

        # 2. ATTEMPT COPY
        print("  Attempting Copy of MainBody...")
        sel = target_doc.Selection
        sel.Clear()
        sel.Add(main_body)
        try:
            sel.Copy()
            print("  Copy SUCCESS.")
        except Exception as e:
            print(f"  Copy FAILED: {e}")
            return

        # 3. PASTE TO NEW PART
        transit_doc = caa.Documents.Add("Part")
        transit_part = transit_doc.Part
        transit_doc.Activate()
        
        sel_target = transit_doc.Selection
        sel_target.Clear()
        sel_target.Add(transit_part)
        try:
            # Using AsResult to avoid 'In-Context' or link issues in the paste
            sel_target.PasteSpecial("AsResult")
            transit_part.Update()
            print("  PasteSpecial AsResult SUCCESS.")
            
            # 4. FINAL EXPORT
            temp_stl = os.path.join(os.environ["TEMP"], "nuke_mainbody_final.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            transit_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"!!! SUCCESS !!! STL generated: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: Export file is empty.")
                
        except Exception as e:
            print(f"  Paste/Export Failed: {e}")

        transit_doc.Close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_mainbody_copy()
