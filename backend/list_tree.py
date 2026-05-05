import win32com.client
import os

def walk(p, depth=0):
    try:
        indent = "  " * depth
        pn = p.PartNumber
        name = p.Name
        print(f"{indent}PartNumber: {pn} | Name: {name}")
        for i in range(1, p.Products.Count + 1):
            walk(p.Products.Item(i), depth + 1)
    except: pass

def main():
    try:
        caa = win32com.client.Dispatch("CATIA.Application")
        doc = caa.ActiveDocument
        print(f"Traversing: {doc.Name}")
        walk(doc.Product)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
