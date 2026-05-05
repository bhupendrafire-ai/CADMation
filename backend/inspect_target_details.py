import sys
from app.services.catia_bridge import catia_bridge

def main():
    caa = catia_bridge.get_application()
    if not caa:
        print("CATIA not connected.")
        return
        
    doc = None
    for i in range(1, caa.Documents.Count + 1):
        if "203_UPPER" in caa.Documents.Item(i).Name:
            doc = caa.Documents.Item(i)
            break
            
    if not doc:
        print("Could not find the target document.")
        return
        
    print(f"Inspecting document: {doc.Name}")
    part = doc.Part
    spa = doc.GetWorkbench("SPAWorkbench")
    sel = doc.Selection
    
    from app.services.geometry_service import geometry_service
    
    def measure(obj):
        try:
            res = geometry_service.get_bounding_box(obj)
            return res.get("stock_size", "Failed")
        except Exception as e:
            return f"Failed: {str(e)}"

    print(f"Whole Part Measurement: {measure(part)}")

    print("\n--- Bodies ---")
    for b in part.Bodies:
        print(f"Body: {b.Name} | Size: {measure(b)}")
        
    print("\n--- HybridBodies ---")
    for hb in part.HybridBodies:
        print(f"HybridBody: {hb.Name} | Size: {measure(hb)}")

if __name__ == "__main__":
    # Ensure standard output is handled without encoding issues
    main()
