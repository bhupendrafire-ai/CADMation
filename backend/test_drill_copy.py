
import win32com.client
import pythoncom
import os

def test_drill_and_copy():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        target_doc = None
        sel = None
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            try:
                if doc.Selection.Count > 0:
                    target_doc = doc
                    sel = doc.Selection
                    break
            except: continue
        
        if not target_doc:
            print("Please select something in CATIA.")
            return

        raw_pop = sel.Item(1).Value
        print(f"Selection: {getattr(raw_pop, 'Name', 'Unknown')} ({type(raw_pop).__name__})")

        # TRY 1: If it's a Product, find its Part
        found_part = None
        try:
            if hasattr(raw_pop, "ReferenceProduct"):
                ref = raw_pop.ReferenceProduct
                print(f"RefProduct: {ref.Name}")
                # Search for a Part in the Parent of the ReferenceProduct
                p = ref.Parent
                # In STEP, the Parent is often a Document-like object
                if hasattr(p, "Part"):
                    found_part = p.Part
                    print(f"Found Part via RefParent: {found_part.Name}")
        except: pass

        if not found_part:
            # TRY 2: Direct Part attribute
            if hasattr(raw_pop, "Part"):
                found_part = raw_pop.Part
                print(f"Found Part via direct attr: {found_part.Name}")

        # If we found a Part, try direct export FIRST
        if found_part:
            print(f"--- Testing Direct Export from {found_part.Name} ---")
            
            # Find the document
            curr = found_part
            source_doc = None
            for _ in range(10):
                if hasattr(curr, "ExportData"):
                    source_doc = curr
                    break
                curr = getattr(curr, "Parent", None)
                if not curr: break

            if source_doc:
                print(f"Source Document for Export: {source_doc.Name}")
                temp_stl = os.path.join(os.environ["TEMP"], "test_direct_drill.stl")
                if os.path.exists(temp_stl): os.remove(temp_stl)
                
                try:
                    source_doc.ExportData(temp_stl, "stl")
                    if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                        print(f"SUCCESS! Direct export worked: {os.path.getsize(temp_stl)} bytes")
                    else:
                        print(f"FAILED: Direct export empty ({os.path.getsize(temp_stl) if os.path.exists(temp_stl) else 'N/A'} bytes)")
                except Exception as e:
                    print(f"Direct export error: {e}")
            else:
                print("Could not find Document object for ExportData.")

            # Still try the Body copy as backup for diagnosis
            print(f"\n--- Retrying Body Copy with 'Paste' (not AsResult) ---")
            transit_doc = caa.Documents.Add("Part")
            transit_part = transit_doc.Part
            sel_target = transit_doc.Selection
            target_doc.Activate()
            sel.Clear()
            sel.Add(found_part.MainBody)
            sel.Copy()
            transit_doc.Activate()
            sel_target.Clear()
            sel_target.Add(transit_part.MainBody)
            try:
                sel_target.Paste() # Standard paste
                transit_part.Update()
                print(f"Standard Paste Shapes: {transit_part.MainBody.Shapes.Count}")
            except Exception as e:
                print(f"Standard Paste Failed: {e}")
            transit_doc.Close()
        else:
            print("FAILED to resolve selection to a Part object.")
            # Let's try to copy the Product itself one more time but into the Part root
            print("--- Final Hail Mary: Copy Product to Part Root ---")
            # (Already did this in previous script, confirmed failed)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_drill_and_copy()
