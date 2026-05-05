"""
Quick script to list the assembly tree structure so we can find
the correct part names for the in-place test.
"""
import sys, os
sys.path.append(os.getcwd())
import win32com.client

catia = win32com.client.Dispatch("CATIA.Application")
doc = catia.ActiveDocument
print(f"Active: {doc.Name}\n")

def dump(prod, depth=0):
    indent = "  " * depth
    subs = prod.Products
    for i in range(1, subs.Count + 1):
        p = subs.Item(i)
        name = p.Name
        pn = ""
        try: pn = p.PartNumber
        except: pn = "?"
        
        # Check if it's a part or sub-assembly
        is_part = False
        try:
            ref = p.ReferenceProduct
            parent_doc = ref.Parent
            if ".CATPart" in parent_doc.Name:
                is_part = True
        except:
            pass
        
        marker = "[PART]" if is_part else "[ASM]"
        print(f"{indent}{marker} {name}  (PN={pn})")
        
        try:
            if p.Products.Count > 0:
                # Only recurse 3 levels deep
                if depth < 3:
                    dump(p, depth+1)
        except:
            pass

dump(doc.Product)
