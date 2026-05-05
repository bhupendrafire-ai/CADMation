import sys
from app.services.geometry_service import geometry_service
from app.services.catia_bridge import catia_bridge

def main():
    caa = catia_bridge.get_application()
    if not caa:
        print("CATIA not connected.")
        return
        
    doc = caa.ActiveDocument
    if "Product" not in doc.Name:
        print(f"Active doc is not a Product: {doc.Name}")
        doc = None
        for i in range(1, caa.Documents.Count + 1):
            if "203_UPPER" in caa.Documents.Item(i).Name:
                doc = caa.Documents.Item(i)
                break
        if not doc:
            print("Could not find the target document.")
            return
    
    prod = doc.Product
    print(f"Testing root product: {prod.Name}")
    
    # Try measuring the product directly
    
    # Try measuring the product directly
    spa = doc.GetWorkbench("SPAWorkbench")
    sel = doc.Selection
    sel.Clear()
    sel.Add(prod)
    if sel.Count > 0:
        val = None
        try:
            val = sel.Item(1).Reference
        except Exception as e:
            print(f"Reference failed: {e}")
            try:
                val = sel.Item(1).Value
            except Exception as e2:
                print(f"Value failed: {e2}")
                
        if val:
            try:
                measurable = spa.GetMeasurable(val)
                bb = [0.0] * 6
                bb = measurable.GetBoundaryBox(bb)
                print(f"Direct SPA bbox on product: {bb}")
            except Exception as e:
                print(f"GetMeasurable failed: {e}")

if __name__ == "__main__":
    main()
