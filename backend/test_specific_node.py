
import win32com.client
import pythoncom
import os

def test_specific_node(search_name):
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        found_target_doc = None
        
        sn = "lower steel" # Generalized search
        print(f"Searching for Document containing: '{sn}'")
        
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if sn in doc.Name.lower().replace("_", " ").replace(".", " "):
                print(f"  FOUND Document: {doc.Name}")
                found_target_doc = doc
                break
        
        if not found_target_doc:
            print(f"FAILED: Could not find Part document matching '{sn}'.")
            return

        # NEW STRATEGY: For STEP documents with internal components, 
        # just export the whole Part doc. It's much safer than Copy-Paste.
        print(f"--- Testing Direct Export of Root Part: {found_target_doc.Name} ---")
        
        if hasattr(found_target_doc, "ExportData"):
            temp_stl = os.path.join(os.environ["TEMP"], "nuke_direct_parent.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            
            try:
                found_target_doc.ExportData(temp_stl, "stl")
                if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                    print(f"SUCCESS! Direct export of parent worked: {os.path.getsize(temp_stl)} bytes")
                    # Analyze the BBox briefly
                    # (In a real app, the backend handles parsing)
                else:
                    print(f"FAILED: Export empty or missing.")
            except Exception as e:
                print(f"Export Error: {e}")
        else:
            print("Document does not support ExportData.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_specific_node("LOWER STEEL")
