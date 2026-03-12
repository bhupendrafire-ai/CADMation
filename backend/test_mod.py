from pycatia import catia
from pycatia.mec_mod_interfaces.part import Part

def modify_verified():
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
        
        print(f"Modifying Part: {part.name}")
        
        target_name = "Radius.22\\Radius"
        target_val = 160.0
        
        found = False
        for param in part.parameters:
            if target_name in param.name:
                print(f"Found parameter: {param.name} (Current: {param.value})")
                param.value = target_val
                print(f"New value set: {param.value}")
                found = True
        
        if found:
            part.update()
            prod.update()
            print("Update triggered in CATIA.")
        else:
            print(f"Parameter '{target_name}' not found in Part parameters.")
            
    except Exception as e:
        print(f"Error during modification: {e}")

if __name__ == "__main__":
    modify_verified()
