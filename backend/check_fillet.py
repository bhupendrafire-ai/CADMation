from pycatia import catia
from pycatia.mec_mod_interfaces.part import Part
import sys

def check_fillet():
    try:
        caa = catia()
        doc = caa.active_document
        prod = doc.product
        comp = prod.products.item('Bottom Die')
        
        # Correct path found
        ref_prod = comp.com_object.ReferenceProduct
        part_doc = ref_prod.Parent
        part_com = part_doc.Part
        part = Part(part_com)
        
        print(f"Checking Part: {part.name}")
        
        fillet_wrapped = part.find_object_by_name('EdgeFillet.3')
        fillet = fillet_wrapped.com_object
        print(f"Found COM feature: {fillet.Name}")
        
        # Try raw COM property access (PascalCase usually)
        try:
            rad = fillet.Radius
            print(f"Current Radius Value (Raw COM): {rad.Value} mm")
        except Exception as e:
            print(f"Could not read .Radius property via COM: {e}")
            # Try to see if it has parameters
            try:
                for i in range(1, fillet.Parameters.Count + 1):
                    p = fillet.Parameters.Item(i)
                    print(f"  Parameter: {p.Name} = {p.Value}")
            except: pass
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_fillet()
