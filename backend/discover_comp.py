from pycatia import catia
import sys

def discover_comp():
    try:
        caa = catia()
        doc = caa.active_document
        prod = doc.product
        comp = prod.products.item('Bottom Die')
        
        print(f"Component Name: {comp.name}")
        com = comp.com_object
        
        # Try to see if it has ReferenceProduct
        try:
            ref_prod = com.ReferenceProduct
            print(f"ReferenceProduct Name: {ref_prod.Name}")
            try:
                parent = ref_prod.Parent
                print(f"Parent Name: {parent.Name}")
                if hasattr(parent, 'Part'):
                    print("Parent HAS .Part property!")
                else:
                    print("Parent does NOT have .Part property.")
            except Exception as e:
                print(f"Could not get Parent: {e}")
        except Exception as e:
            print(f"Could not get ReferenceProduct: {e}")
            
        # Try GetPart
        try:
            part = com.GetPart()
            print(f"com.GetPart() succeeded! Part Name: {part.Name}")
        except Exception as e:
            print(f"com.GetPart() failed: {e}")

        # Try to see all methods/properties via COM
        # We can't easily list COM members in python without advanced stuff, but we can try common ones
        
    except Exception as e:
        print(f"General error: {e}")

if __name__ == "__main__":
    discover_comp()
