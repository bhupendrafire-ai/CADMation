import logging
import sys
import os
import win32com.client

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge

logging.basicConfig(level=logging.INFO)

def detail_debug():
    print("\n=== Detailed Extraction Debug ===")
    caa = catia_bridge.get_application()
    if not caa: return
    
    doc = caa.ActiveDocument
    print(f"Active Document: {doc.Name} ({doc.FullName})")
    
    if hasattr(doc, "Product"):
        root = doc.Product
        print(f"Root Product: {root.Name}")
        
        def explore(prod, depth=0):
            indent = "  " * depth
            count = prod.Products.Count
            print(f"{indent}> Product: {prod.Name} (Children: {count})")
            
            for i in range(1, count + 1):
                child = prod.Products.Item(i)
                try:
                    ref_prod = child.ReferenceProduct
                    parent_doc = ref_prod.Parent
                    doc_name = parent_doc.Name
                    doc_type = type(parent_doc).__name__
                    
                    print(f"{indent}  - Child: {child.Name}")
                    print(f"{indent}    RefDoc: {doc_name} | Type: {doc_type}")
                    
                    # Check if we can get Part
                    if hasattr(parent_doc, "Part"):
                        print(f"{indent}    [PART DETECTED]")
                    
                    explore(child, depth + 1)
                except Exception as e:
                    print(f"{indent}  - Child: {child.Name} | ERROR: {e}")

        explore(root)

if __name__ == "__main__":
    detail_debug()
