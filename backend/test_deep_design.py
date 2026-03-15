
import win32com.client
import pythoncom
import os
import time

def force_deep_design_mode():
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

        print(f"Deep Design Mode unlock for: {target_doc.Name}")
        target_doc.Activate()
        
        # 1. SELECT PRODUCT NODE (The key for Design Mode)
        # Even Part documents have a .Product property if opened in an assembly context
        selection = target_doc.Selection
        selection.Clear()
        
        prod = None
        try:
            prod = target_doc.Product
            selection.Add(prod)
            print("  Selected Document Product.")
        except:
            print("  Could not find .Product on document. Trying .Part...")
            try:
                selection.Add(target_doc.Part)
                print("  Selected Document Part.")
            except:
                print("  Selection failed.")
                return

        # 2. TRIGGER DESIGN MODE
        print("  Triggering 'Design Mode' command...")
        try:
            # We use the specific command name
            caa.StartCommand("Design Mode")
            # CRITICAL: We MUST wait for geometry to load
            print("  Waiting 5 seconds for geometry load...")
            time.sleep(5)
            print("  Finished waiting.")
        except Exception as e:
            print(f"  Command failing: {e}")

        # 3. TEST GEOMETRY ACCESS
        part = target_doc.Part
        target_name = "LOWER STEEL_1"
        found_body = None
        for b in part.Bodies:
            if target_name.lower().replace("_", " ") in b.Name.lower().replace("_", " "):
                found_body = b
                break
        
        if not found_body:
            print("  Target body STILL not found after Design Mode.")
            return

        print(f"  Target found: {found_body.Name}. Testing Copy...")
        selection.Clear()
        selection.Add(found_body)
        try:
            selection.Copy()
            print("  !!! SUCCESS !!! Copy allowed after Deep Design Mode.")
            
            # Final proof: Paste to new part
            transit = caa.Documents.Add("Part")
            transit.Selection.Add(transit.Part)
            transit.Selection.PasteSpecial("AsResult")
            transit.Part.Update()
            
            temp_stl = os.path.join(os.environ["TEMP"], "nuke_deep_design_success.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            transit.ExportData(temp_stl, "stl")
            print(f"  STL generated: {os.path.getsize(temp_stl)} bytes")
            transit.Close()
            
        except Exception as e:
            print(f"  Copy STILL FAILED: {e}")
            print("  This suggests the node is 'Visualization' and 'Design Mode' command didn't work OR it's a restricted 'Result' node.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    force_deep_design_mode()
