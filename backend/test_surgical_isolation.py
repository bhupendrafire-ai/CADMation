
import win32com.client
import pythoncom
import os
import time

def test_surgical_isolation():
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

        print(f"Surgical Isolation in Doc: {target_doc.Name}")
        target_doc.Activate()
        part = target_doc.Part
        target_name = "LOWER STEEL_1"
        
        # 1. FIND TARGET BODY
        target_item = None
        for b in part.Bodies:
            if target_name.lower().replace("_", " ") in b.Name.lower().replace("_", " "):
                target_item = b
                break
        
        if not target_item:
            print(f"FAILED: Body '{target_name}' not found.")
            return

        print(f"FOUND: {target_item.Name}. Attempting Isolate...")

        # 2. ISOLATE via StartCommand
        # We must select it first
        selection = target_doc.Selection
        selection.Clear()
        selection.Add(target_item)
        
        try:
            # 'Isolate' is the command for results with links
            caa.StartCommand("Isolate")
            time.sleep(2) # Wait for isolation
            print("  Isolate command sent.")
            part.Update()
        except Exception as e:
            print(f"  Isolate command failed: {e}")

        # 3. TEST COPY NOW
        # If isolation worked, Copy should be allowed
        try:
            selection.Clear()
            selection.Add(target_item)
            selection.Copy()
            print("  Copy SUCCESS after Isolation.")
        except Exception as e:
            print(f"  Copy still FAILED after Isolation: {e}")
            # If it still fails, it's not a link issue, it's a visualization issue
            return

        # 4. PASTE TO NEW PART
        transit_doc = caa.Documents.Add("Part")
        transit_part = transit_doc.Part
        transit_doc.Activate()
        
        sel_target = transit_doc.Selection
        sel_target.Clear()
        sel_target.Add(transit_part)
        try:
            sel_target.PasteSpecial("AsResult")
            transit_part.Update()
            print("  Paste SUCCESS.")
            
            # 5. FINAL EXPORT
            temp_stl = os.path.join(os.environ["TEMP"], "nuke_surgical_isolated.stl")
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
    test_surgical_isolation()
