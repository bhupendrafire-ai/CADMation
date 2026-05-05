import win32com.client
import pythoncom

def survey():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        print(f"CATIA Version: {catia.Caption}")
        
        if catia.Documents.Count == 0:
            print("No documents open.")
            return

        for i in range(1, catia.Documents.Count + 1):
            doc = catia.Documents.Item(i)
            print(f"\nDocument [{i}]: {doc.Name} ({type(doc)})")
            
            # Try to find a Part
            part = None
            if hasattr(doc, "Part"): 
                part = doc.Part
            else:
                # Check for Product
                try:
                    p = doc.Product
                    print(f"  Product found: {p.Name}")
                    if p.Products.Count > 0:
                        first_inst = p.Products.Item(1)
                        print(f"  First Instance: {first_inst.Name}")
                        try:
                            part = first_inst.ReferenceProduct.Parent.Part
                        except: pass
                except: pass
            
            if part:
                print(f"  Part found: {part.Name}")
                if part.Bodies.Count > 0:
                    print(f"  Bodies: {part.Bodies.Count}")
                    for j in range(1, min(part.Bodies.Count + 1, 5)):
                        print(f"    Body [{j}]: {part.Bodies.Item(j).Name}")
            else:
                print("  No Part found in this document.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    survey()
