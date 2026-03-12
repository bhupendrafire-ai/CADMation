from pycatia import catia
from pycatia.mec_mod_interfaces.part import Part

def synchronize_holes():
    try:
        caa = catia()
        doc = caa.active_document
        prod = doc.product
        
        # Target Top Die
        top_die = None
        for p in prod.products:
            if "Top Die" in p.name:
                top_die = p
                break
        
        if not top_die:
            print("Top Die not found")
            return
            
        # Get Part (Verified path)
        com_part = top_die.com_object.ReferenceProduct.Parent.Part
        part = Part(com_part)
        
        print(f"Synchronizing Features in Part: {part.name}")
        
        # We target all 4 identified radius parameters in Sketch.2
        targets = ["Radius.22\\Radius", "Radius.23\\Radius", "Radius.26\\Radius", "Radius.27\\Radius"]
        target_val = 160.0
        
        updated_count = 0
        for param in part.parameters:
            for t in targets:
                if t in param.name:
                    print(f"Found parameter: {param.name} (Current: {param.value})")
                    param.value = target_val
                    print(f"  -> Set to: {param.value}")
                    updated_count += 1
        
        if updated_count > 0:
            print(f"Total parameters updated: {updated_count}")
            try:
                part.update()
                prod.update()
                print("Update triggered in CATIA.")
            except Exception as e:
                print(f"Update encountered expected warning/error: {e}")
        else:
            print(f"None of the target parameters {targets} were found.")
            
    except Exception as e:
        print(f"Error during synchronization: {e}")

if __name__ == "__main__":
    synchronize_holes()
