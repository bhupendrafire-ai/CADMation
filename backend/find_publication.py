import win32com.client
import sys

def find_publication():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        def find_product(prod, name):
            if name.upper() in prod.Name.upper() or name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_product(prod.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        input_part = find_product(doc.Product, "INPUT PART_01")
        if not input_part:
            print("INPUT PART_01 not found.")
            return

        print(f"Checking Publications in {input_part.Name}...")
        try:
            # Publications on a Product
            pubs = input_part.Publications
            print(f"Total Publications: {pubs.Count}")
            for i in range(1, pubs.Count + 1):
                pub = pubs.Item(i)
                print(f"  Publication [{i}]: {pub.Name}")
                if "AP_AXIS" in pub.Name.upper():
                    print(f"  SUCCESS! Found AP_AXIS Publication.")
                    return pub
        except Exception as e:
            print(f"Error accessing publications: {e}")

        # Try ReferenceProduct publications
        try:
            ref_pubs = input_part.ReferenceProduct.Publications
            print(f"Total Reference Publications: {ref_pubs.Count}")
            for i in range(1, ref_pubs.Count + 1):
                pub = ref_pubs.Item(i)
                print(f"  Ref Publication [{i}]: {pub.Name}")
                if "AP_AXIS" in pub.Name.upper():
                    print(f"  SUCCESS! Found AP_AXIS in Reference Publications.")
                    return pub
        except: pass

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_publication()
