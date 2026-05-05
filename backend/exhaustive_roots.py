import sys, os, time
import win32com.client
import pythoncom

def exhaustive_roots():
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
            print("No Bodies.")
            return

        all_bodies = []
        body_names = set()
        for i in range(1, test_obj.Bodies.Count + 1):
            b = test_obj.Bodies.Item(i)
            all_bodies.append(b)
            body_names.add(b.Name)

        consumed = set()

        print(f"Exhaustive Scan: {len(all_bodies)} bodies...")
        for b in all_bodies:
            for j in range(1, b.Shapes.Count + 1):
                s = b.Shapes.Item(j)
                # Check EVERY property of the shape!
                # This is a bit risky but we can try common ones.
                props = ["Body", "Operand", "TargetBody", "FirstOperand", "SecondOperand"]
                for prop in props:
                    try:
                        op = getattr(s, prop)
                        if op.Name in body_names:
                            consumed.add(op.Name)
                    except: pass
        
        print("\n--- ALL ROOTS FOUND ---")
        for b in all_bodies:
            if b.Name not in consumed:
                print(f"ROOT: {b.Name}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    exhaustive_roots()
