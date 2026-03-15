
import win32com.client
import pythoncom
import os
import time

def test_measure():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        # Try to find a part or product to measure
        # We'll just try to measure the first product if it's an assembly
        if "Product" in doc.Name:
            target = doc.Product.Products.Item(1)
            print(f"Targeting Product: {target.Name}")
        else:
            target = doc.Part
            print(f"Targeting Part: {target.Name}")
            
        # Manually simulate the Copy-Paste logic
        target_doc = caa.Documents.Add("Part")
        target_part = target_doc.Part
        
        source_doc = doc
        sel_source = source_doc.Selection
        sel_target = target_doc.Selection
        
        sel_source.Clear()
        sel_source.Add(target)
        print(f"Added to source selection: {sel_source.Count}")
        
        try:
            print(f"Source item name: {getattr(target, 'Name', 'Unknown')}")
            
            # STAGE 1: Direct Export
            print("--- Stage 1: Direct Export ---")
            orig_alerts = caa.DisplayFileAlerts
            caa.DisplayFileAlerts = False
            try:
                if hasattr(target, "ApplyDesignMode"): target.ApplyDesignMode()
                if hasattr(target, "Update"): target.Update()
            except: pass
            
            temp_stl = os.path.join(os.environ['TEMP'], "test_nuclear_stage1.stl")
            if os.path.exists(temp_stl): os.remove(temp_stl)
            
            # Need to find the doc
            t_doc = target
            for _ in range(10):
                if hasattr(t_doc, "ExportData"): break
                t_doc = getattr(t_doc, "Parent", None)
                if not t_doc: break
                
            if t_doc and hasattr(t_doc, "ExportData"):
                try:
                    t_doc.Activate()
                    t_doc.ExportData(temp_stl, "stl")
                    print(f"Direct export size: {os.path.getsize(temp_stl)} bytes")
                except Exception as e:
                    print(f"Direct export failed: {e}")
            
            caa.DisplayFileAlerts = orig_alerts
            
            # STAGE 2: Copy/Paste (if stage 1 empty)
            if not os.path.exists(temp_stl) or os.path.getsize(temp_stl) < 100:
                print("--- Stage 2: Copy-Paste Flattening ---")
                sel_source.Clear()
                sel_source.Add(target)
                sel_source.Copy()
                
                target_doc.Activate()
                sel_target.Clear()
                sel_target.Add(target_part.MainBody)
                sel_target.PasteSpecial("AsResult")
                target_part.Update()
                
                print(f"Shapes in transient part: {target_part.MainBody.Shapes.Count}")
                if target_part.MainBody.Shapes.Count > 0:
                    temp_stl_v2 = os.path.join(os.environ['TEMP'], "test_nuclear_stage2.stl")
                    target_doc.ExportData(temp_stl_v2, "stl")
                    print(f"Copy-Paste export size: {os.path.getsize(temp_stl_v2)} bytes")
            
        except Exception as e:
            print(f"Diagnostic failed: {e}")

            # Format 2: CATPrtResultWithOutLink (More robust for parts)
            if target_part.MainBody.Shapes.Count == 0:
                print("--- Testing CATPrtResultWithOutLink ---")
                sel_target.Clear()
                sel_target.Add(target_part.MainBody)
                try:
                    sel_target.PasteSpecial("CATPrtResultWithOutLink")
                    target_part.Update()
                    print(f"OutLink Paste - Shapes: {target_part.MainBody.Shapes.Count}")
                except Exception as e:
                    print(f"OutLink failed: {e}")

            # Format 3: Simple Paste (If result fails)
            if target_part.MainBody.Shapes.Count == 0:
                print("--- Testing Simple Paste ---")
                sel_target.Clear()
                sel_target.Add(target_part.MainBody)
                try:
                    sel_target.Paste()
                    target_part.Update()
                    print(f"Simple Paste - Shapes: {target_part.MainBody.Shapes.Count}")
                except Exception as e:
                    print(f"Simple Paste failed: {e}")

            # FINAL CHECK
            if target_part.MainBody.Shapes.Count > 0:
                temp_stl = os.path.join(os.environ['TEMP'], "test_nuke_v2.stl")
                target_doc.ExportData(temp_stl, "stl")
                print(f"STL Size: {os.path.getsize(temp_stl)} bytes")
            else:
                print("FAILED: All paste methods resulted in 0 shapes.")
            
        except Exception as e:
            print(f"Diagnostic failed: {e}")
            
        # target_doc.Close() # Leave open for inspection
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_measure()
