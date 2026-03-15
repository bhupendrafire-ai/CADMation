
import win32com.client
import pythoncom
import os
import time

def test_surgical_body():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # 1. Target the document (Search FLEXIBLY)
        target_doc = None
        target_body = None
        target_key = "lower steel"
        
        print(f"Searching for Body containing: '{target_key}' in {caa.Documents.Count} docs...")
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            # Prioritize original STEP if open
            if "op 20" in doc.Name.lower():
                print(f"  Scanning Assembly: {doc.Name}")
                # Assemblies might have sub-products that are actually bodies if we drill down
                # But let's check for CATParts first
            
            if hasattr(doc, "Part"):
                p = doc.Part
                for b in p.Bodies:
                    if target_key in b.Name.lower():
                        target_doc = doc
                        target_body = b
                        break
            if target_doc: break
        
        if not target_doc or not target_body:
            print("FAILED: Target body not found in any open document.")
            return

        print(f"Found Target: {target_body.Name} in {target_doc.Name}")
        target_doc.Activate()

        # 2. THE UNLOCK (Design Mode)
        print("  Applying Design Mode to unlock geometry...")
        try:
            # Most robust way to wake up a STEP import's geometry
            target_doc.Product.ApplyDesignMode()
            time.sleep(3)
            print("  Design Mode Applied via API.")
        except Exception as e:
            print(f"  API ApplyDesignMode failed: {e}. Trying StartCommand...")
            try:
                caa.StartCommand("Design Mode")
                time.sleep(3)
            except: pass

        # 3. THE EXTRACTION (Nuclear Copy-Paste)
        transit_doc = caa.Documents.Add("Part")
        transit_part = transit_doc.Part
        
        target_doc.Activate()
        sel_source = target_doc.Selection
        sel_source.Clear()
        sel_source.Add(target_body)
        try:
            sel_source.Copy()
            print("  Copy SUCCESS.")
        except Exception as e:
            print(f"  Copy FAILED: {e}")
            # Final desperate attempt: Isolate the node if possible via UI
            transit_doc.Close()
            return

        transit_doc.Activate()
        sel_target = transit_doc.Selection
        sel_target.Clear()
        sel_target.Add(transit_part)
        try:
            # Flatten it
            sel_target.PasteSpecial("AsResult")
            transit_part.Update()
            print("  PasteSpecial AsResult SUCCESS.")
            
            # 4. EXPORT
            temp_stl = os.path.join(os.environ["TEMP"], "nuke_surgical_body_final.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            transit_doc.ExportData(temp_stl, "stl")
            
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"!!! SUCCESS !!! STL generated: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: STL is empty or missing.")
                
        except Exception as e:
            print(f"  Extraction Logic Failed: {e}")
        
        transit_doc.Close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_surgical_body()
