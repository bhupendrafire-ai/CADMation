from pycatia import catia
from pycatia.mec_mod_interfaces.part import Part

def check_sketches():
    caa = catia()
    doc = caa.active_document
    prod = doc.product
    
    # Target Top Die
    found = None
    for p in prod.products:
        if "Top Die" in p.name:
            found = p
            break
            
    if not found:
        print("Top Die not found")
        return
        
    com_part = found.com_object.ReferenceProduct.Parent.Part
    part = Part(com_part)
    print(f"Part: {part.name}")
    
    # Check if Part has sketches (hallucination check)
    try:
        count = part.sketches.count
        print(f"Success: part.sketches exists, count={count}")
    except Exception as e:
        print(f"Direct part.sketches failed: {e}")
        
    # Check Bodies -> Sketches
    print("\nChecking Bodies for sketches:")
    for body in part.bodies:
        try:
            sk_count = body.sketches.count
            print(f"  Body '{body.name}' has {sk_count} sketches.")
            for i in range(1, sk_count + 1):
                sk = body.sketches.item(i)
                print(f"    - Sketch: {sk.name}")
        except Exception as e:
            print(f"  Body '{body.name}' sketches access failed: {e}")
            
    # Check Hybrid Bodies -> Sketches
    print("\nChecking Hybrid Bodies for sketches:")
    for hbody in part.hybrid_bodies:
        try:
            # Sketches in HybridBodies?
            sk_count = hbody.hybrid_sketches.count # Might be hybrid_sketches or similar
            print(f"  HybridBody '{hbody.name}' has {sk_count} sketches.")
        except:
            # Try plain hybrid_shapes iteration
            sk_count = 0
            for shape in hbody.hybrid_shapes:
                if "Sketch" in shape.name:
                    sk_count += 1
            print(f"  HybridBody '{hbody.name}' has {sk_count} items with 'Sketch' in name.")

if __name__ == "__main__":
    check_sketches()
