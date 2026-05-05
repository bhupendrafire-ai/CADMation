import sys, os, time
import win32com.client
import pythoncom

def find_root_bodies():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        
        target = doc
        if hasattr(doc, "Product") and doc.Product.Products.Count > 0:
            target = doc.Product.Products.Item(1)
        
        test_obj = target
        if hasattr(test_obj, "ReferenceProduct"):
            try:
                ref = test_obj.ReferenceProduct
                if hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                    test_obj = ref.Parent.Part
            except: pass
        if hasattr(test_obj, "Part"): test_obj = test_obj.Part
        
        if not hasattr(test_obj, "Bodies"):
            print("No Bodies collection.")
            return

        all_bodies = []
        for i in range(1, test_obj.Bodies.Count + 1):
            all_bodies.append(test_obj.Bodies.Item(i))

        # Map to track which bodies are 'consumed' as operands
        consumed_bodies = set()

        print(f"Analyzing {len(all_bodies)} bodies for Boolean dependencies...")
        
        for b in all_bodies:
            try:
                # Check shapes for Boolean operations (Add, Remove, Intersect)
                # In CATIA COM, Boolean operations have a property 'Body' or 'Operand'
                for j in range(1, b.Shapes.Count + 1):
                    shape = b.Shapes.Item(j)
                    s_type = type(shape).__name__
                    
                    # Add, Assemble, Remove, Intersect are typical booleans
                    if any(x in s_type for x in ["Add", "Assemble", "Remove", "Intersect", "Boolean"]):
                        try:
                            # The operand body is the one being Booleanned into 'b'
                            op = shape.Body
                            consumed_bodies.add(op.Name)
                        except: pass
            except: pass

        print("\n--- ROOT BODIES (Top Level in Tree) ---")
        root_count = 0
        for b in all_bodies:
            if b.Name not in consumed_bodies:
                root_count += 1
                print(f"ROOT [{root_count}]: {b.Name}")
        
        if root_count == 0:
            print("No roots found? Checking MainBody...")
            print(f"MainBody: {test_obj.MainBody.Name}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    find_root_bodies()
