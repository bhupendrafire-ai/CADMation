import win32com.client
import os

def debug_export_and_tree():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        target_name = "NE152000C001"
        
        def find_product(parent, name):
            for i in range(1, parent.Products.Count + 1):
                child = parent.Products.Item(i)
                if name.lower() in child.Name.lower() or name.lower() in child.PartNumber.lower():
                    return child
                res = find_product(child, name)
                if res: return res
            return None
            
        target = find_product(doc.Product, target_name)
        if not target:
            print("Target not found")
            return
            
        print(f"Target Resolved: {target.Name}")
        
        part = target.ReferenceProduct.Parent.Part
        part_doc = part.Parent
        
        # Try activating the window
        try:
            # Find window with part name
            win = None
            for i in range(1, caa.Windows.Count + 1):
                if target.Name in caa.Windows.Item(i).Caption or target.PartNumber in caa.Windows.Item(i).Caption:
                    win = caa.Windows.Item(i)
                    break
            
            if win:
                win.Activate()
                print(f"Activated Window: {win.Caption}")
            else:
                # If no window, it might be internal (STEP single doc)
                pass
        except: pass

        # Attempt Export again
        temp_stl = "C:\\Temp\\debug_active.stl"
        if os.path.exists(temp_stl): os.remove(temp_stl)
        
        try:
            print(f"Attempting ExportData on {part_doc.Name}")
            part_doc.ExportData(temp_stl, "stl")
            if os.path.exists(temp_stl):
                print(f"SUCCESS: STL exported with size {os.path.getsize(temp_stl)}")
            else:
                print("FAILED: STL file not created even with activation.")
        except Exception as e:
            print(f"Export Error: {e}")

        # Deep Tree Inspection
        print("\n--- Tree Inspection ---")
        def inspect_part(p):
            print(f"Part: {p.Name}")
            print(f" Bodies: {p.Bodies.Count}")
            for i in range(1, p.Bodies.Count + 1):
                b = p.Bodies.Item(i)
                print(f"  Body {i}: {b.Name}")
                try:
                    for j in range(1, b.Shapes.Count + 1):
                        s = b.Shapes.Item(j)
                        print(f"    Shape {j}: {s.Name} (Type: {type(s)})")
                except: pass
            
            print(f" HybridBodies: {p.HybridBodies.Count}")
            for i in range(1, p.HybridBodies.Count + 1):
                hb = p.HybridBodies.Item(i)
                print(f"  HB {i}: {hb.Name}")
                try:
                    for j in range(1, hb.HybridShapes.Count + 1):
                        hs = hb.HybridShapes.Item(j)
                        print(f"    HS {j}: {hs.Name} (Type: {type(hs)})")
                except: pass

        inspect_part(part)

    except Exception as e:
        print(f"Debug Failed: {e}")

if __name__ == "__main__":
    debug_export_and_tree()
