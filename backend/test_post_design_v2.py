
import win32com.client
import pythoncom
import os
import time

def test_isolated_export():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # 1. FIND DOCUMENT
        target_doc = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if "lower_steel" in doc.Name.lower():
                target_doc = doc
                break
        
        if not target_doc:
            print("FAILED: Could not find LOWER_STEEL document.")
            return

        print(f"Isolating Component in Doc: {target_doc.Name}")
        target_doc.Activate()
        part = target_doc.Part
        target_name = "LOWER STEEL_1"
        
        # 2. FIND TARGET BODY
        target_item = None
        # Search in Bodies
        for b in part.Bodies:
            if target_name.lower().replace("_", " ") in b.Name.lower().replace("_", " "):
                target_item = b
                break
        
        if not target_item:
            print(f"FAILED: Body '{target_name}' not found.")
            return

        print(f"FOUND: {target_item.Name}. Starting Isolation Protocol...")

        # 3. COPY-PASTE TO NEW PART
        transit_doc = caa.Documents.Add("Part")
        transit_part = transit_doc.Part
        
        target_doc.Activate()
        sel_source = target_doc.Selection
        sel_source.Clear()
        sel_source.Add(target_item)
        try:
            sel_source.Copy()
        except Exception as e:
            print(f"  Copy Error: {e}")
            transit_doc.Close()
            return

        transit_doc.Activate()
        sel_target = transit_doc.Selection
        sel_target.Clear()
        sel_target.Add(transit_part)
        try:
            sel_target.PasteSpecial("AsResult")
            transit_part.Update()
            print("  PasteSpecial AsResult SUCCESS.")
        except Exception as e:
            print(f"  PasteSpecial Failed: {e}. Trying standard Paste...")
            try:
                sel_target.Paste()
                transit_part.Update()
                print("  Standard Paste SUCCESS.")
            except Exception as e2:
                print(f"  Standard Paste also failed: {e2}")
                transit_doc.Close()
                return

        # 4. BREAK CONTEXT: SAVE AS CATPART, CLOSE, REOPEN
        temp_catpart = os.path.join(os.environ["TEMP"], "iso_final_v5.CATPart")
        if os.path.exists(temp_catpart): os.remove(temp_catpart)
        
        print(f"  Saving isolated Part to {temp_catpart}...")
        transit_doc.SaveAs(temp_catpart)
        transit_doc.Close()
        
        time.sleep(2) # Give Windows/CATIA a breather
        
        print("  Re-opening isolated Part for final export...")
        clean_doc = caa.Documents.Open(temp_catpart)
        clean_doc.Activate()
        
        # 5. FINAL EXPORT TO STL
        temp_stl = os.path.join(os.environ["TEMP"], "nuke_final_success.stl")
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        try:
            clean_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"!!! SUCCESS !!! STL generated: {os.path.getsize(temp_stl)} bytes")
                print(f"Location: {temp_stl}")
            else:
                print("FAILED: Export file is empty or missing.")
        except Exception as e:
            print(f"FINAL Export Error: {e}")
            
        clean_doc.Close()
        print("Done.")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    test_isolated_export()
