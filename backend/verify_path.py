from pycatia import catia

def check_path():
    caa = catia()
    doc = caa.active_document
    prod = doc.product
    
    # Try to find "Top Die"
    found = None
    for p in prod.products:
        if "Top Die" in p.name:
            found = p
            break
            
    if not found:
        print("Top Die not found")
        return
        
    print(f"Testing component: {found.name}")
    try:
        # Test 1: reference_product.parent.part (pycatia style)
        p1 = found.reference_product.parent.part
        print(f"Path 1 (pycatia) success: {p1.name}")
    except Exception as e:
        print(f"Path 1 failed: {e}")
        
    try:
        # Test 2: com_object style
        p2 = found.com_object.ReferenceProduct.Parent.Part
        print(f"Path 2 (COM Pascal) success: {p2.Name}")
    except Exception as e:
        print(f"Path 2 failed: {e}")

if __name__ == "__main__":
    check_path()
