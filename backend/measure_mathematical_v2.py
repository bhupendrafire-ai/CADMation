import win32com.client
import math
import os
import time

def measure_math_v2():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        def find_obj(root, name):
            if name.upper() in root.Name.upper(): return root
            try:
                for i in range(1, root.Products.Count + 1):
                    r = find_obj(root.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        print("Locating Targets...")
        plate = find_obj(doc.Product, "202_LOWER PLATE")
        input_part = find_obj(doc.Product, "INPUT PART_01")
        
        if not plate or not input_part: return
        
        # Get Publication -> Axis System
        pub = input_part.Publications.Item("AP_AXIS")
        axis_sys = pub.ValuatedElement
        print(f"Axis System: {axis_sys.Name}")

        # Extract Basis
        o, vx, vy = [0.0]*3, [0.0]*3, [0.0]*3
        try:
            axis_sys.GetOrigin(o)
            axis_sys.GetVectors(vx, vy)
        except Exception as e:
            print(f"GetVectors failed: {e}")
            # Fallback: check if it's the absolute axis
            o, vx, vy = [0,0,0], [1,0,0], [0,1,0]

        print(f"Basis: O={o}, X={vx}, Y={vy}")

        def norm(v):
            l = math.sqrt(sum(x*x for x in v))
            return [x/l for x in v] if l > 0 else None
        
        def cross(a, b):
            return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

        ex = norm(vx) or [1,0,0]
        ey_raw = norm(vy) or [0,1,0]
        ez = norm(cross(ex, ey_raw))
        ey = norm(cross(ez, ex))

        # STL Export
        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        stl_path = os.path.join(temp_dir, f"math_v2_{int(time.time())}.stl")
        plate.ReferenceProduct.Parent.ExportData(stl_path, "stl")

        # Project vertices
        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        
        with open(stl_path, 'r') as f:
            for line in f:
                if "vertex" in line.lower():
                    pts = line.split()
                    if len(pts) >= 4:
                        px, py, pz = float(pts[1]), float(pts[2]), float(pts[3])
                        dx, dy, dz = px - o[0], py - o[1], pz - o[2]
                        tx = dx*ex[0] + dy*ex[1] + dz*ex[2]
                        ty = dx*ey[0] + dy*ey[1] + dz*ey[2]
                        tz = dx*ez[0] + dy*ez[1] + dz*ez[2]
                        xmin, ymin, zmin = min(xmin, tx), min(ymin, ty), min(zmin, tz)
                        xmax, ymax, zmax = max(xmax, tx), max(ymax, ty), max(zmax, tz)

        width = xmax - xmin
        depth = ymax - ymin
        height = zmax - zmin
        
        print("\nROUGH STOCK RESULT (MATH):")
        print(f"DX: {width:.2f} mm")
        print(f"DY: {depth:.2f} mm")
        print(f"DZ: {height:.2f} mm")
        
        dims = sorted([width, depth, height], reverse=True)
        print(f"Final Reported Size: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm")

        if os.path.exists(stl_path): os.remove(stl_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_math_v2()
