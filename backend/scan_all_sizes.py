import win32com.client
from app.services.geometry_service import geometry_service

def walk(p):
    try:
        # Check if it's a part instance
        ref_doc = p.ReferenceProduct.Parent
        if hasattr(ref_doc, "Part"):
            part = ref_doc.Part
            res = geometry_service.get_bounding_box(part)
            size = res.get("stock_size", "N/A")
            # Log all parts, but highlight ones near the 155 value
            if "155" in size or "203_UPPER" in p.Name or "203_UPPER" in p.PartNumber:
                 print(f"MATCH -> PN: {p.PartNumber} | Name: {p.Name} | Size: {size}")
            else:
                 print(f"PN: {p.PartNumber} | Name: {p.Name} | Size: {size}")
        
        for i in range(1, p.Products.Count + 1):
            walk(p.Products.Item(i))
    except: pass

def main():
    try:
        caa = win32com.client.Dispatch("CATIA.Application")
        doc = caa.ActiveDocument
        print(f"Scanning all parts in {doc.Name}...")
        walk(doc.Product)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
