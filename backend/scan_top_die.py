from pycatia import catia
from pycatia.mec_mod_interfaces.part import Part
import sys

def scan_top_die():
    try:
        caa = catia()
        doc = caa.active_document
        prod = doc.product
        comp = None
        for p in prod.products:
            if "Top Die" in p.name:
                comp = p
                print(f"Found component: {p.name}")
                break
        
        if not comp:
            print("Top Die not found in assembly!")
            return

        # Helper logic (manual version)
        ref_prod = comp.com_object.ReferenceProduct
        part_com = ref_prod.Parent.Part
        part = Part(part_com)
        
        print(f"Scanning Part: {part.name}")
        
        # Scan ALL shapes in Bodies
        print("--- Bodies ---")
        for body in part.bodies:
            for shape in body.shapes:
                try:
                    com = shape.com_object
                    val = None
                    if hasattr(com, "Radius"): val = com.Radius.Value
                    if hasattr(com, "Diameter"): val = com.Diameter.Value
                    if val is not None:
                        print(f"  Shape: {shape.name} | Value: {val}")
                except:
                    pass
                    
        # Scan Hybrid Bodies (GSD)
        print("--- Hybrid Bodies ---")
        for hbody in part.hybrid_bodies:
            for shape in hbody.hybrid_shapes:
                try:
                    com = shape.com_object
                    val = None
                    if hasattr(com, "Radius"): val = com.Radius.Value
                    if hasattr(com, "Diameter"): val = com.Diameter.Value
                    if val is not None:
                        print(f"  HybridShape: {shape.name} | Value: {val}")
                except:
                    pass

        # Scan Parameters
        print("--- Parameters ---")
        for param in part.parameters:
            try:
                if "Radius" in param.name or "Diameter" in param.name:
                    print(f"  Param: {param.name} | Value: {param.value}")
            except:
                pass
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scan_top_die()
