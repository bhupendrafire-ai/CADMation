
import win32com.client
import pythoncom
import os
import time

def test_visibility_isolation():
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

        print(f"Using Visibility Isolation in Doc: {target_doc.Name}")
        target_doc.Activate()
        part = target_doc.Part
        target_name = "LOWER STEEL_1"
        
        # 1. HIDE ALL BODIES
        selection = target_doc.Selection
        vis_interface = selection.VisProperties
        
        print("Hiding all Bodies and HybridBodies...")
        selection.Clear()
        for b in part.Bodies:
            selection.Add(b)
        for hb in part.HybridBodies:
            selection.Add(hb)
        
        # 1 = catVisPropertyShowAttr (Hide)
        # 0 = catVisPropertyShow (Show)
        selection.VisProperties.SetShow(1) 
        selection.Clear()

        # 2. SHOW SPECIFIC TARGET
        found_target = None
        print(f"Searching for target: {target_name}")
        for b in part.Bodies:
            if target_name.lower().replace("_", " ") in b.Name.lower().replace("_", " "):
                found_target = b
                break
        
        if not found_target:
            print("FAILED: Target body not found.")
            return

        print(f"Showing: {found_target.Name}")
        selection.Add(found_target)
        selection.VisProperties.SetShow(0)
        selection.Clear()
        
        part.Update()

        # 3. EXPORT DOCUMENT
        temp_stl = os.path.join(os.environ["TEMP"], "nuke_visibility_final.stl")
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        print("Exporting Document with visibility isolation...")
        try:
            target_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"!!! SUCCESS !!! STL generated: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: Export file is empty. Visibility isolation might not work with ExportData 'stl' in some CATIA configs.")
        except Exception as e:
            print(f"Export Error: {e}")

        # CLEANUP: Show everything again (don't leave user with hidden parts)
        selection.Clear()
        for b in part.Bodies: selection.Add(b)
        for hb in part.HybridBodies: selection.Add(hb)
        selection.VisProperties.SetShow(0)
        selection.Clear()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_visibility_isolation()
