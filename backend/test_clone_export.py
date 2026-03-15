
import win32com.client
import pythoncom
import os
import time

def test_clone_and_export():
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

        print(f"Cloning Document: {target_doc.Name}")
        
        # 1. SAVE CLONE
        temp_clone = os.path.join(os.environ["TEMP"], "nuke_clone_isolation.CATPart")
        if os.path.exists(temp_clone): os.remove(temp_clone)
        
        try:
            # We must use SaveAs to a NEW path to break ties
            target_doc.SaveAs(temp_clone)
            print(f"  Clone saved to {temp_clone}")
        except Exception as e:
            print(f"  SaveAs Failed (Doc might be read-only or locked): {e}")
            # If SaveAs fails, we try a different path: Documents.Read
            return

        # 2. OPEN CLONE (Bypasses the original's assembly context)
        # We don't close the original yet to avoid destabilizing CATIA
        clone_doc = caa.Documents.Open(temp_clone)
        clone_doc.Activate()
        
        # 3. EXPORT CLONE
        temp_stl = os.path.join(os.environ["TEMP"], "nuke_clone_final.stl")
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        print("  Exporting from standalone clone...")
        try:
            clone_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"!!! SUCCESS !!! STL generated: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: Export file is empty.")
        except Exception as e:
            print(f"  Export Error: {e}")
            
        # 4. CLEANUP
        clone_doc.Close()
        # We should probably delete the temp_clone but let's leave it for manual check if failed
        print("Done.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_clone_and_export()
