import win32com.client
import sys
import os

def debug_meas():
    try:
        caa = win32com.client.Dispatch("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        if sel.Count == 0:
            print("Please select something in CATIA first.")
            return

        obj = sel.Item(1).Value
        print(f"Selected: {obj.Name} (Type: {type(obj)})")
        
        try:
            wb = doc.GetWorkbench("SPAWorkbench")
            print("SPAWorkbench obtained.")
            
            # Technique 1: Direct OLE object
            try:
                m = wb.GetMeasurable(obj)
                print("Technique 1 (Direct) Success.")
            except Exception as e:
                print(f"Technique 1 (Direct) Failed: {e}")
                
            # Technique 2: CreateReferenceFromObject (Part only)
            try:
                if hasattr(doc, "Part"):
                    ref = doc.Part.CreateReferenceFromObject(obj)
                    m = wb.GetMeasurable(ref)
                    print("Technique 2 (Part Ref) Success.")
                else:
                    print("Technique 2 skipped (Not a Part document).")
            except Exception as e:
                print(f"Technique 2 (Part Ref) Failed: {e}")
                
            # Technique 5: STL Export Test
            try:
                temp_stl = os.path.join(os.environ["TEMP"], "debug_test.stl")
                if os.path.exists(temp_stl): os.remove(temp_stl)
                print(f"Testing STL Export to: {temp_stl}")
                
                # Try 1: Selection export (Face)
                sel.Clear()
                sel.Search("Type=Face,all")
                print(f"Faces found: {sel.Count}")
                if sel.Count > 0:
                    sel.ExportData(temp_stl, "stl")
                    if os.path.exists(temp_stl):
                        print(f"STL Export (Faces) Success, Size: {os.path.getsize(temp_stl)}")
                        os.remove(temp_stl)
                
                # Try 2: Selection export (All)
                sel.Clear()
                sel.Search("Type=*,all")
                print(f"Items found (all): {sel.Count}")
                sel.ExportData(temp_stl, "stl")
                if os.path.exists(temp_stl):
                    print(f"STL Export (All) Success, Size: {os.path.getsize(temp_stl)}")
            except Exception as e:
                print(f"STL Export Test Failed: {e}")

        except Exception as e:
            print(f"SPA Workbench/Measurable Error: {e}")
            
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    debug_meas()
