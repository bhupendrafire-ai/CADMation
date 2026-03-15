
import win32com.client
import pythoncom
import os
import time

def test_apply_design_mode():
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

        print(f"Applying Design Mode via API for: {target_doc.Name}")
        target_doc.Activate()
        
        # 1. GET PRODUCT
        prod = target_doc.Product
        
        # 2. APPLY DESIGN MODE (API call)
        print("  Calling prod.ApplyDesignMode()...")
        try:
            prod.ApplyDesignMode()
            print("  API call successful. Waiting for geometry load...")
            time.sleep(5)
        except Exception as e:
            print(f"  API call failed: {e}")

        # 3. TEST COPY
        part = target_doc.Part
        target_name = "LOWER STEEL_1"
        target_item = None
        for b in part.Bodies:
            if target_name.lower().replace("_", " ") in b.Name.lower().replace("_", " "):
                target_item = b
                break
        
        if not target_item:
            print(f"  FAILED: Body '{target_name}' not found.")
            return

        print(f"  Attempting Copy of {target_item.Name}...")
        sel = target_doc.Selection
        sel.Clear()
        sel.Add(target_item)
        try:
            sel.Copy()
            print("  !!! SUCCESS !!! Copy allowed after ApplyDesignMode API.")
            
            # Proof of Paste
            transit = caa.Documents.Add("Part")
            transit.Selection.Add(transit.Part)
            transit.Selection.PasteSpecial("AsResult")
            transit.Part.Update()
            
            temp_stl = os.path.join(os.environ["TEMP"], "nuke_apply_design_final.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            transit.ExportData(temp_stl, "stl")
            print(f"  STL generated: {os.path.getsize(temp_stl)} bytes")
            transit.Close()
            
        except Exception as e:
            print(f"  Copy STILL FAILED: {e}")
            print("  This confirms the geometry is blocked by 'Result' restrictions, not just Visualization Mode.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_apply_design_mode()
