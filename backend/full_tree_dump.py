
import win32com.client
import sys

def dump_tree_full():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
    except:
        print("CATIA not found.")
        return

    doc = caa.ActiveDocument
    print(f"Document: {doc.Name}")
    
    def walk(prod, depth=0):
        print(f"{'  '*depth}- {prod.Name} (PartNumber: {getattr(prod, 'PartNumber', 'N/A')})")
        try:
            for i in range(1, prod.Products.Count + 1):
                walk(prod.Products.Item(i), depth + 1)
        except: pass

    walk(doc.Product)

if __name__ == "__main__":
    dump_tree_full()
