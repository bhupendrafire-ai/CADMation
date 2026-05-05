import sys, os, time
import win32com.client
import pythoncom

def aggressive_dependency_check():
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

        print(f"Aggressive Scan: {len(all_bodies)} bodies...")
        for b in all_bodies:
            for j in range(1, b.Shapes.Count + 1):
                s = b.Shapes.Item(j)
                # Try all common names for operand properties
                for prop in ["Body", "Operand", "TargetBody", "FirstOperand", "SecondOperand"]:
                    try:
                        op = getattr(s, prop)
                        if op.Name in body_names and op.Name != b.Name:
                            consumed.add(op.Name)
                            # print(f"  {b.Name} consumes {op.Name} via {prop}")
                    except: pass
        
        print("\n--- DETECTED ROOTS ---")
        roots = []
        for b in all_bodies:
            if b.Name not in consumed:
                roots.append(b.Name)
        
        for idx, r in enumerate(roots):
            print(f"[{idx+1}] {r}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    aggressive_dependency_check()
