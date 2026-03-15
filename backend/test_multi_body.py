
import win32com.client
import pythoncom
import os
import time

def test_context_breaker_multi_body():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # 1. Target the document (Search FLEXIBLY for 'steel')
        target_doc = None
        target_key = "steel"
        print(f"Searching for Body containing: '{target_key}' in {caa.Documents.Count} docs...")
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if hasattr(doc, "Part"):
                p = doc.Part
                for b in p.Bodies:
                    if target_key in b.Name.lower():
                        target_doc = doc
                        break
            if target_doc: break
        
        if not target_doc:
            print(f"FAILED: Could not find any document with a body containing '{target_key}'.")
            target_doc = caa.ActiveDocument
            print(f"Using ActiveDocument: {target_doc.Name}")

        print(f"Original Doc: {target_doc.Name}")
        
        # 2. THE CONTEXT BREAKER (Save standalone copy)
        temp_dir = os.environ["TEMP"]
        standalone_path = os.path.join(temp_dir, "measure_context_breaker.CATPart")
        if os.path.exists(standalone_path): os.remove(standalone_path)
        
        print(f"  Breaking Context... Saving standalone copy to {standalone_path}")
        try:
            target_doc.SaveAs(standalone_path)
        except Exception as e:
            print(f"  Critical: SaveAs failed (Doc might be locked): {e}")
            return

        # 3. OPEN THE STANDALONE (Fresh Window, No Context)
        print("  Opening clean standalone document...")
        clean_doc = caa.Documents.Open(standalone_path)
        clean_doc.Activate()
        part = clean_doc.Part
        selection = clean_doc.Selection
        
        # 4. HIDE ALL GEOMETRY
        print("  Hiding all geometry in clean doc...")
        selection.Clear()
        for b in part.Bodies: selection.Add(b)
        for hb in part.HybridBodies: selection.Add(hb)
        try:
            selection.VisProperties.SetShow(1) # Hide
            selection.Clear()
        except: pass

        # 5. ITERATIVE MEASUREMENT
        bodies_to_measure = [b for b in part.Bodies if b.Shapes.Count > 0]
        print(f"  Measuring {len(bodies_to_measure)} isolated bodies...")

        success_count = 0
        for i, body in enumerate(bodies_to_measure):
            print(f"    [{i+1}/{len(bodies_to_measure)}] Body: {body.Name}")
            
            # Show target
            selection.Clear()
            selection.Add(body)
            selection.VisProperties.SetShow(0) # Show
            selection.Clear()
            
            part.Update()
            
            # Export (Now it will work because we are in a standalone document!)
            temp_stl = os.path.join(temp_dir, f"measure_clean_body_{i}.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            
            try:
                clean_doc.ExportData(temp_stl, "stl")
                if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                    print(f"      SUCCESS: {os.path.getsize(temp_stl)} bytes")
                    success_count += 1
                else:
                    print("      FAILED: STL empty.")
            except Exception as e:
                print(f"      Export Error: {e}")
                
            # Hide again
            selection.Clear()
            selection.Add(body)
            selection.VisProperties.SetShow(1) # Hide
            selection.Clear()

        # CLEANUP
        clean_doc.Close()
        print(f"\nTOTAL SUCCESS: {success_count} bodies measured individually.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_context_breaker_multi_body()
