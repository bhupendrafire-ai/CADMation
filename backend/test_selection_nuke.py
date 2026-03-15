
import win32com.client
import pythoncom
import os

def test_current_selection():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        
        # Robustly find a selection
        target_doc = None
        sel = None
        
        # Try active doc first
        if caa.Documents.Count > 0:
            doc = caa.ActiveDocument
            if doc.Selection.Count > 0:
                target_doc = doc
                sel = doc.Selection
                print(f"Selection found in Active Document: {doc.Name}")
        
        # Search others if not found
        if not target_doc:
            for i in range(1, caa.Documents.Count + 1):
                doc = caa.Documents.Item(i)
                try:
                    if doc.Selection.Count > 0:
                        target_doc = doc
                        sel = doc.Selection
                        print(f"Selection found in Document {i}: {doc.Name}")
                        break
                except: continue
        
        if target_doc and sel:
            print(f"Target Document: {target_doc.Name}")
            print(f"Selection Count: {sel.Count}")
            
            raw_pop = sel.Item(1).Value
            item_name = getattr(raw_pop, "Name", "Unknown")
            print(f"Selected Item: {item_name} (Type: {type(raw_pop).__name__})")

            # Try to drill down from Product to Part
            source_to_copy = raw_pop
            try:
                # If it's a Product, its 'Part' might be accessible via specific properties
                if hasattr(raw_pop, "ReferenceProduct"):
                    ref_prod = raw_pop.ReferenceProduct
                    # In some assemblies, there's a Part hidden under the Product
                    # We can try to use the 'Part' property if it's a leaf node
                    # But often we just use the Product for selection
                    pass
            except: pass

            formats = ["AsResult", "CATPrtResultWithOutLink", "Paste"]
            
            for fmt in formats:
                print(f"\n--- Testing Format: {fmt} (Target: Part Root) ---")
                transit_doc = caa.Documents.Add("Part")
                transit_part = transit_doc.Part
                sel_target = transit_doc.Selection
                
                target_doc.Activate()
                sel.Clear()
                sel.Add(source_to_copy)
                sel.Copy()
                
                transit_doc.Activate()
                sel_target.Clear()
                # TARGET THE PART ITSELF, NOT THE MAINBODY
                sel_target.Add(transit_part)
                
                try:
                    sel_target.PasteSpecial(fmt)
                    transit_part.Update()
                    
                    # Inspect results across the whole part
                    shapes = 0
                    for body in transit_part.Bodies:
                        shapes += body.Shapes.Count
                    
                    hybrids = transit_part.HybridBodies.Count
                    print(f"  - Total Shapes: {shapes}, Hybrids: {hybrids}")
                    if shapes > 0 or hybrids > 0:
                        print(f"  - SUCCESS with format {fmt} on Part Root!")
                except Exception as e:
                    print(f"  - FAILED with format {fmt}: {e}")
                
                transit_doc.Close()
                target_doc.Activate()

        else:
            print("Please select something in CATIA before running this test.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_current_selection()
