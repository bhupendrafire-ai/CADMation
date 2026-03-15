import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def find_prod(p, name):
    if name.upper() in p.Name.upper(): return p
    try:
        for i in range(1, p.Products.Count + 1):
            res = find_prod(p.Products.Item(i), name)
            if res: return res
    except: pass
    return None

def inspect_non_std():
    target_name = "LWR NON STD PART"
    caa = catia_bridge.get_application()
    if not caa: return
    
    doc = caa.ActiveDocument
    root = doc.Product
    
    target = find_prod(root, target_name)
    if not target:
        print(f"Could not find {target_name}")
        # List immediate children of root to see if I'm even close
        print("\nRoot Children:")
        for i in range(1, root.Products.Count + 1):
            print(f"  {i}: {root.Products.Item(i).Name}")
        return
        
    print(f"INSPECTING: {target.Name}")
    print(f"Child Count: {target.Products.Count}")
    
    for i in range(1, target.Products.Count + 1):
        child = target.Products.Item(i)
        print(f"\n[{i}] Child Name: {child.Name}")
        try:
            # Check if it has a reference
            ref_prod = child.ReferenceProduct
            print(f"    Ref: {ref_prod.Name}")
            
            # Check if it has geometry
            try:
                spa = doc.GetWorkbench("SPAWorkbench")
                # Try to get inertia for mass
                inertia = spa.GetInertia(child)
                print(f"    Mass: {inertia.Mass:.3f} kg")
            except:
                print("    No inertia data")
                
            # Check for Part
            try:
                ref_doc = ref_prod.Parent
                if hasattr(ref_doc, "Part"):
                    print(f"    Type: CATPart ({ref_doc.Name})")
                else:
                    print(f"    Type: CATProduct Sub-Asm ({ref_doc.Name})")
            except:
                print("    Internal Component / No doc back-ref")

        except Exception as e:
            print(f"    ERROR: {e}")

if __name__ == "__main__":
    inspect_non_std()
