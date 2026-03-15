import win32com.client
import pythoncom
import math

def test_inertia():
    try:
        caa = win32com.client.Dispatch("CATIA.Application")
        part_doc = None
        for i in range(1, caa.Documents.Count + 1):
            d = caa.Documents.Item(i)
            if ".CATPart" in d.Name:
                part_doc = d
                break
        
        if not part_doc:
            print("No CATPart found.")
            return

        print(f"Testing Part: {part_doc.Name}")
        part = part_doc.Part
        
        spa = part_doc.GetWorkbench("SPAWorkbench")
        ref = part.CreateReferenceFromObject(part.MainBody)
        
        print("Adding Inertia analysis...")
        inertias = spa.Inertias
        inertia = inertias.Add(ref)
        
        mass = inertia.Mass
        print(f"Mass: {mass:.3f} kg")
        
        princ = [0.0, 0.0, 0.0]
        # In win32com, out parameters are returned as a tuple
        res = inertia.GetPrincipalMoments(princ)
        print(f"Principal Moments: {res}")
        
        if isinstance(res, tuple) and len(res) == 3:
            i1, i2, i3 = res[0], res[1], res[2]
            if mass > 0:
                a_sq = 6.0 * (i2 + i3 - i1) / mass
                b_sq = 6.0 * (i1 + i3 - i2) / mass
                c_sq = 6.0 * (i1 + i2 - i3) / mass
                
                a = math.sqrt(max(0, a_sq)) * 1000
                b = math.sqrt(max(0, b_sq)) * 1000
                c = math.sqrt(max(0, c_sq)) * 1000
                
                dims = sorted([a, b, c], reverse=True)
                print(f"Calculated Dimensions (mm): {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_inertia()
