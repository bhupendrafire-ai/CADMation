import win32com.client

def walk(p):
    try:
        pn = p.PartNumber
        name = p.Name
        print(f"PN: {pn} | Name: {name}")
        for i in range(1, p.Products.Count + 1):
            walk(p.Products.Item(i))
    except: pass

def main():
    try:
        caa = win32com.client.Dispatch("CATIA.Application")
        doc = caa.ActiveDocument
        walk(doc.Product)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
