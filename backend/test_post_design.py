
import win32com.client
import pythoncom
import os

def test_post_design():
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

        print(f"Isolating Component in Doc: {target_doc.Name}")
        
        # 1. Ensure we have the path to re-open if needed
        doc_path = ""
        try: doc_path = target_doc.FullName
        except: pass
        
        target_doc.Activate()
        part = target_doc.Part
        target_item = None
        target_name = "LOWER STEEL_1"
        
        # Search for the body
        for b in list(part.Bodies) + list(part.HybridBodies):
            if target_name.lower().replace("_", " ") in b.Name.lower().replace("_", " "):
                target_item = b
                break
        
        if not target_item:
            print("FAILED: Target item not found.")
            return

        # 2. THE ISOLATION PROTOCOL
        print(f"Starting Isolation Protocol for {target_item.Name}...")
        
        # Create Transient Part
        transit_doc = caa.Documents.Add("Part")
        transit_part = transit_doc.Part
        temp_catpart = os.path.join(os.environ["TEMP"], "nuke_isolation_temp.CATPart")
        if os.path.exists(temp_catpart): os.remove(temp_catpart)
        
        # Copy-Paste with 'In-Context' protection
        target_doc.Activate()
        sel_source = target_doc.Selection
        sel_source.Clear()
        sel_source.Add(target_item)
        sel_source.Copy()
        
        transit_doc.Activate()
        sel_target = transit_doc.Selection
        sel_target.Clear()
        sel_target.Add(transit_part)
        try:
            sel_target.PasteSpecial("AsResult")
            transit_part.Update()
            print("  Paste SUCCESS. Saving to temp CATPart...")
        except Exception as e:
            print(f"  Paste Failed: {e}. Isolation might be incomplete.")
            transit_doc.Close()
            return

        # 3. SAVE AND RE-OPEN (This breaks ALL context links)
        transit_doc.SaveAs(temp_catpart)
        transit_doc.Close()
        
        time.sleep(1)
        isolated_doc = caa.Documents.Open(temp_catpart)
        isolated_doc.Activate()
        
        # 4. FINAL EXPORT from isolated file
        temp_stl = os.path.join(os.environ["TEMP"], "nuke_isolated_final.stl")
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        try:
            isolated_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"SUCCESS! Isolated STL generated: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: Isolated export yielded nothing.")
        except Exception as e:
            print(f"Export Error: {e}")
            
        isolated_doc.Close()
        print("Isolation Protocol Complete.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_post_design()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_geometry_and_copy()
