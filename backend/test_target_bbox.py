import sys
import os
from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service

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
        
    print(f"Target document found: {doc.Name}")
    
    # Check if it's a part or product
    if "Part" in doc.Name:
        target = doc.Part
        print("It's a Part.")
    else:
        target = doc.Product
        print("It's a Product.")
        
    res = geometry_service.get_bounding_box(target)
    print(f"Geometry Service BBox on whole part: {res['stock_size']}")
    
    with open("result_bbox.txt", "w") as f:
        f.write(f"BBox: {res['stock_size']}\n")

if __name__ == "__main__":
    main()
