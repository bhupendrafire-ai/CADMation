
import win32com.client
import sys
import os

def inspect():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
    except:
        print("CATIA not found.")
        return

    doc = caa.ActiveDocument
    print(f"Active Document: {doc.Name}")
    
    # Traverse to find 1229
    def find_item(prod, name):
        if name in prod.Name: return prod
        for i in range(1, prod.Products.Count + 1):
            res = find_item(prod.Products.Item(i), name)
            if res: return res
        return None

    target = find_item(doc.Product, "1229")
    if not target:
        print("Target '1229' not found in tree.")
        return

    print(f"Found Target: {target.Name} (Type: {type(target)})")
    
    # Try Tier 1 logic exactly as in service
    print("\n--- Testing Tier 1 Logic ---")
    try:
        spa = doc.GetWorkbench("SPAWorkbench")
        sel = doc.Selection
        sel.Clear()
        sel.Add(target)
        print(f"Selection Count: {sel.Count}")
        if sel.Count > 0:
            item = sel.Item(1)
            print(f"Item Type: {str(type(item))}")
            
            try:
                ref = item.Reference
                print(f"Reference: {ref.Name}")
                m = spa.GetMeasurable(ref)
                bb = [0.0]*6
                bb = m.GetBoundaryBox(bb)
                print(f"Measured via Reference: {bb}")
            except Exception as e:
                print(f"Failed via Reference: {e}")
                
            try:
                val = item.Value
                print(f"Value: {val.Name}")
                m = spa.GetMeasurable(val)
                bb = [0.0]*6
                bb = m.GetBoundaryBox(bb)
                print(f"Measured via Value: {bb}")
            except Exception as e:
                print(f"Failed via Value: {e}")
                
    except Exception as e:
        print(f"General failure: {e}")

    # Inspect ReferenceProduct
    print("\n--- Inspecting ReferenceProduct ---")
    try:
        ref_prod = target.ReferenceProduct
        print(f"ReferenceProduct: {ref_prod.Name}")
        ref_doc = ref_prod.Parent
        print(f"Parent: {ref_doc.Name}")
        
        if hasattr(ref_doc, "Part"):
            part = ref_doc.Part
            spa = ref_doc.GetWorkbench("SPAWorkbench")
            body = part.MainBody
            print(f"MainBody: {body.Name}")
            
            # Technique 4: CreateReferenceFromObject
            try:
                ref = part.CreateReferenceFromObject(body)
                m = spa.GetMeasurable(ref)
                bb = [0.0]*6
                bb = m.GetBoundaryBox(bb)
                print(f"Measured via CreateReferenceFromObject: {bb}")
            except Exception as e:
                print(f"Failed via CreateReferenceFromObject: {e}")
                
            # Technique 5: Selection.Add + GetMeasurable(item.Reference) in LOCAL doc
            try:
                sel_loc = ref_doc.Selection
                sel_loc.Clear()
                sel_loc.Add(body)
                ref_sel = sel_loc.Item(1).Reference
                m = spa.GetMeasurable(ref_sel)
                bb = [0.0]*6
                bb = m.GetBoundaryBox(bb)
                print(f"Measured via Selection.Reference in local doc: {bb}")
            except Exception as e:
                print(f"Failed via Local Selection: {e}")
    except Exception as e:
        print(f"ReferenceProduct access failed: {e}")

    # Deep Inspection of Part Structure
    try:
        ref_doc = target.ReferenceProduct.Parent
        if hasattr(ref_doc, "Part"):
            part = ref_doc.Part
            print(f"\n--- Deep Part Inspection for {ref_doc.Name} ---")
            print(f"MainBody: {part.MainBody.Name}")
            print(f"Bodies Count: {part.Bodies.Count}")
            for i in range(1, part.Bodies.Count + 1):
                b = part.Bodies.Item(i)
                print(f"  Body({i}): {b.Name} (Shapes: {b.Shapes.Count})")
                
            print(f"HybridBodies Count: {part.HybridBodies.Count}")
            for i in range(1, part.HybridBodies.Count + 1):
                hb = part.HybridBodies.Item(i)
                print(f"  HybridBody({i}): {hb.Name}")
                
            print(f"GeometricSets Count: {part.HybridShapeFactory.GeometricSets.Count if hasattr(part, 'HybridShapeFactory') else 'N/A'}")
            
    except Exception as e:
        print(f"Deep inspection failed: {e}")

if __name__ == "__main__":
    inspect()
