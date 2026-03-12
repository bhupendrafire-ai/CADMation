from pycatia import catia

def check_bridge():
    caa = catia()
    doc = caa.active_document
    prod = doc.product
    
    print(f"Product: {prod.name}")
    for i in range(1, prod.products.count + 1):
        child = prod.products.item(i)
        print(f"\nComponent: {child.name}")
        
        try:
            # Try to bridge to Part via COM
            com_child = child.com_object
            ref_prod = com_child.ReferenceProduct
            parent_doc = ref_prod.Parent
            print(f"  Ref Doc: {parent_doc.Name}")
            
            if ".CATPart" in parent_doc.Name:
                part = parent_doc.Part
                print(f"  Success! Part identified: {part.Name}")
                print(f"  Bodies count: {part.Bodies.Count}")
                for j in range(1, part.Bodies.Count + 1):
                    print(f"    - Body: {part.Bodies.Item(j).Name}")
        except Exception as e:
            print(f"  Bridge failed: {e}")

if __name__ == "__main__":
    check_bridge()
