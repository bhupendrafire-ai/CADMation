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
        
    prod = doc.Product
    print(f"Testing root product: {prod.Name}")
    
    if prod.Products.Count > 0:
        child = prod.Products.Item(1)
        print(f"Child 1: {child.Name}")
        try:
            pos = child.Position
            components = [0.0] * 12
            components = pos.GetComponents(components)
            print(f"Position components: {components}")
        except Exception as e:
            print(f"Failed to get position: {e}")

if __name__ == "__main__":
    main()
