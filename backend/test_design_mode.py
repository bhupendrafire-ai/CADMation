
import win32com.client
import pythoncom
import os

def force_design_mode_and_test():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # 1. Targeted search for LOWER_STEEL
        target_doc = None
        print(f"Scanning {caa.Documents.Count} documents...")
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            # Check both name and path
            dn = doc.Name.lower()
            df = ""
            try: df = doc.FullName.lower()
            except: pass
            
            if "lower_steel" in dn or "lower steel" in dn or "lower_steel" in df:
                target_doc = doc
                break
            
            if i % 20 == 0:
                print(f"  ...checked {i} docs...")
        
        if not target_doc:
            print("FAILED: Could not find LOWER_STEEL document in the full list.")
            return

        print(f"Found Doc: {target_doc.Name}")
        target_doc.Activate()
        
        # 2. FORCE DESIGN MODE via Selection
        print("Forcing Design Mode...")
        sel = caa.ActiveDocument.Selection
        sel.Clear()
        sel.Add(target_doc.Product)
        try:
            # This is the secret command to force Design Mode on a Visualization node
            caa.StartCommand("Design Mode")
            # Wait a bit for CATIA to process
            import time
            time.sleep(2)
            print("Design Mode command sent.")
        except Exception as e:
            print(f"StartCommand Error: {e}")

        # 3. Test Export again
        print("Testing Export after Design Mode...")
        temp_stl = os.path.join(os.environ["TEMP"], "nuke_design_mode.stl")
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        try:
            # We must be in a Part document context for STL export to work well
            # If the doc is a Product, we export the Product
            target_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl) and os.path.getsize(temp_stl) > 100:
                print(f"SUCCESS! STL generated: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: Export still empty. Checking shapes...")
                if hasattr(target_doc, "Part"):
                    p = target_doc.Part
                    print(f"  Part Shapes: {sum(b.Shapes.Count for b in p.Bodies)}")
        except Exception as e:
            print(f"Export Error: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    force_design_mode_and_test()
