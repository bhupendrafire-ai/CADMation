
import win32com.client
import pythoncom
import os
import time

def test_newfrom_isolation():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        clone_path = os.path.join(os.environ["TEMP"], "nuke_clone_isolation.CATPart")
        
        # 1. CLOSE EXISTING IF OPEN
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if "nuke_clone_isolation" in doc.Name.lower():
                doc.Close()
                print("Closed existing clone.")
                break
        
        time.sleep(1)
        
        # 2. NEW FROM (Breaks ALL context links)
        print(f"Creating NewFrom: {clone_path}")
        # Note: NewFrom returns a Document object
        try:
            new_doc = caa.Documents.NewFrom(clone_path)
            new_doc.Activate()
            print(f"New Document Created: {new_doc.Name}")
        except Exception as e:
            print(f"NewFrom FAILED: {e}")
            return

        part = new_doc.Part
        target_name = "LOWER STEEL_1"
        found_body = None
        for b in part.Bodies:
            if target_name.lower() in b.Name.lower():
                found_body = b
                break
        
        if not found_body:
            print(f"Body {target_name} not found in new document.")
            new_doc.Close()
            return

        print(f"Found Body: {found_body.Name}. Testing Export...")
        
        # 3. SURGICAL VISIBILITY EXPORT
        # Hide everything but the target
        selection = new_doc.Selection
        selection.Clear()
        for b in part.Bodies: selection.Add(b)
        selection.VisProperties.SetShow(1) # Hide
        selection.Clear()
        
        selection.Add(found_body)
        selection.VisProperties.SetShow(0) # Show
        selection.Clear()
        
        part.Update()
        
        # 4. FINAL EXPORT
        temp_stl = os.path.join(os.environ["TEMP"], "nuke_final_newfrom.stl")
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        try:
            new_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"!!! SUCCESS !!! STL generated from NewFrom: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: STL empty or missing.")
        except Exception as e:
            print(f"Export Error: {e}")
            
        new_doc.Close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_newfrom_isolation()
