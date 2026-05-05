import win32com.client
import math
import os
import time

def get_basis(caa, pub):
    try:
        # Get the underlying element
        axis_sys = pub.ValuatedElement
        print(f"Valuated Element: {axis_sys.Name}")
        
        origin = [0.0, 0.0, 0.0]
        vx = [0.0, 0.0, 0.0]
        vy = [0.0, 0.0, 0.0]
        
        # Robust COM access for out-params
        axis_sys.GetOrigin(origin)
        axis_sys.GetVectors(vx, vy)
        
        print(f"Origin: {origin}")
        print(f"X-Vector: {vx}")
        print(f"Y-Vector: {vy}")
        
        # Normalize and find Z
        def norm(v):
            l = math.sqrt(sum(x*x for x in v))
            return [x/l for x in v] if l > 0 else None
        
        def cross(a, b):
            return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

        ex = norm(vx) or [1,0,0]
        ey_raw = norm(vy) or [0,1,0]
        ez = norm(cross(ex, ey_raw))
        ey = norm(cross(ez, ex))
        
        return origin, ex, ey, ez
    except Exception as e:
        print(f"Basis extraction failed: {e}")
        return None

def measure_math():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        def find_obj_by_name(root, target_name):
            if target_name.upper() in root.Name.upper(): return root
            try:
                for i in range(1, root.Products.Count + 1):
                    r = find_obj_by_name(root.Products.Item(i), target_name)
                    if r: return r
            except: pass
            return None

        # 1. Get Targets
        plate = find_obj_by_name(doc.Product, "202_LOWER PLATE")
        input_part = find_obj_by_name(doc.Product, "INPUT PART_01")
        
        pub = None
        if input_part:
            try: pub = input_part.Publications.Item("AP_AXIS")
            except: pass
        
        if not plate or not pub:
            print("Targets not found.")
            return

        # 2. Get Basis
        basis = get_basis(caa, pub)
        if not basis: return
        o, ex, ey, ez = basis

        # 3. Export STL
        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        stl_path = os.path.join(temp_dir, f"math_measure_{int(time.time())}.stl")
        plate.ReferenceProduct.Parent.ExportData(stl_path, "stl")

        # 4. Calculate oriented BB
        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        
        with open(stl_path, 'r') as f:
            for line in f:
                if "vertex" in line.lower():
                    pts = line.split()
                    if len(pts) >= 4:
                        px, py, pz = float(pts[1]), float(pts[2]), float(pts[3])
                        # Vector relative to origin
                        dx, dy, dz = px - o[0], py - o[1], pz - o[2]
                        # Projected into local frame
                        tx = dx*ex[0] + dy*ex[1] + dz*ex[2]
                        ty = dx*ey[0] + dy*ey[1] + dz*ey[2]
                        tz = dx*ez[0] + dy*ez[1] + dz*ez[2]
                        xmin, ymin, zmin = min(xmin, tx), min(ymin, ty), min(zmin, tz)
                        xmax, ymax, zmax = max(xmax, tx), max(ymax, ty), max(zmax, tz)

        width = xmax - xmin
        depth = ymax - ymin
        height = zmax - zmin
        
        print("\n==============================")
        print("ORIENTED BOUNDING BOX RESULTS (AP_AXIS)")
        print("==============================")
        print(f"DX (Width) : {width:.3f} mm")
        print(f"DY (Depth) : {depth:.3f} mm")
        print(f"DZ (Height): {height:.3f} mm")
        
        dims = sorted([width, depth, height], reverse=True)
        print(f"Final Size: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm")

        if os.path.exists(stl_path): os.remove(stl_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_math()
