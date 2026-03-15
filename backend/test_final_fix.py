
import win32com.client
import pythoncom
import os
import time

def final_surgical_fix():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # 1. Target the document (from selection or list)
        target_doc = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if "lower_steel" in doc.Name.lower():
                target_doc = doc
                break
        
        if not target_doc:
            print("FAILED: Document not found.")
            return

        print(f"Final Surgical Fix for: {target_doc.Name}")
        
        # 2. THE NUCLEAR UNLOCK: Save a Standalone Copy
        # This breaks all assembly-level "In-Context" and "Visualization" propagation locks
        temp_dir = os.environ["TEMP"]
        temp_catpart = os.path.join(temp_dir, "nuke_fix_isolated.CATPart")
        if os.path.exists(temp_catpart): os.remove(temp_catpart)
        
        print("  Breaking Assembly Locks... Saving standalone copy...")
        try:
            target_doc.SaveAs(temp_catpart)
        except Exception as e:
            print(f"  SaveAs Failed: {e}. If it's a STEP result, we must force a different path.")
            # Fallback: Just Try a direct Document Export since we are desperate
            temp_stl = os.path.join(temp_dir, "nuke_desperation.stl")
            target_doc.ExportData(temp_stl, "stl")
            print(f"  Desperation Export Result: {os.path.exists(temp_stl)}")
            return

        # 3. OPEN THE CLONE
        iso_doc = caa.Documents.Open(temp_catpart)
        iso_doc.Activate()
        iso_part = iso_doc.Part
        
        # 4. FORCE DESIGN MODE ON THE CLONE
        print("  Forcing Design Mode on standalone clone...")
        try:
            iso_doc.Selection.Add(iso_doc.Product)
            caa.StartCommand("Design Mode")
            time.sleep(3)
        except: pass
        
        # 5. SURGICAL EXTRACTION of 'LOWER STEEL_1'
        target_name = "LOWER STEEL_1"
        found_body = None
        for b in iso_part.Bodies:
            if target_name.lower().replace("_", " ") in b.Name.lower().replace("_", " "):
                found_body = b
                break
        
        if not found_body:
            print(f"  FAILED: {target_name} not found in clone.")
            iso_doc.Close()
            return

        # 6. COPY-PASTE TO FINAL TRANSIENT
        print(f"  Copying {found_body.Name} from clone...")
        final_doc = caa.Documents.Add("Part")
        final_part = final_doc.Part
        
        iso_doc.Activate()
        iso_doc.Selection.Clear()
        iso_doc.Selection.Add(found_body)
        iso_doc.Selection.Copy()
        
        final_doc.Activate()
        final_doc.Selection.Add(final_part)
        final_doc.Selection.PasteSpecial("AsResult")
        final_part.Update()
        
        # 7. EXPORT
        final_stl = os.path.join(temp_dir, "nuke_final_victory.stl")
        if os.path.exists(final_stl): os.remove(final_stl)
        final_doc.ExportData(final_stl, "stl")
        
        if os.path.exists(final_stl) and os.path.getsize(final_stl) > 100:
            print(f"!!! TOTAL VICTORY !!! STL generated: {os.path.getsize(final_stl)} bytes")
        else:
            print("FAILED: Even the nuclear isolation failed. Geometry is non-solid.")

        final_doc.Close()
        iso_doc.Close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    final_surgical_fix()
