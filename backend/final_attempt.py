import win32com.client
import sys
import os
import math
import time

def get_basis_v3():
    try:
        # Use gencache for better out-param support
        from win32com.client import gencache
        # We'll try to find the AxisSystem type info
        # But for now, we'll use a more robust list of lists
        
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        def find_product(prod, name):
            if name.upper() in prod.Name.upper() or name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_product(prod.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        input_part = find_product(doc.Product, "INPUT PART_01")
        if not input_part:
            print("INPUT PART_01 not found.")
            return

        part = input_part.ReferenceProduct.Parent.Part
        ax = None
        for i in range(1, part.AxisSystems.Count + 1):
            if "AP_AXIS" in part.AxisSystems.Item(i).Name.upper():
                ax = part.AxisSystems.Item(i)
                break
        
        if not ax:
            print("AP_AXIS not found in INPUT PART_01.")
            return

        print(f"Axis Found: {ax.Name}")
        
        # Try to get data directly using VARIANTs if needed, or check if it is just [0,0,0]
        o = [0.0, 0.0, 0.0]
        ax.GetOrigin(o)
        
        vx = [0.0, 0.0, 0.0]
        vy = [0.0, 0.0, 0.0]
        try:
            ax.GetVectors(vx, vy)
        except: pass
        
        print(f"Origin: {o}")
        print(f"X: {vx}")
        print(f"Y: {vy}")

        if sum(math.fabs(x) for x in vx) < 0.001:
            print("COULD NOT GET AXIS VECTORS. Assuming absolute identity.")
            vx, vy = [1,0,0], [0,1,0]

        # Calculate Z and normalize
        def norm(v):
            l = math.sqrt(sum(x*x for x in v))
            return [x/l for x in v] if l > 0 else None
        
        def cross(a, b):
            return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

        ex = norm(vx)
        ey_raw = norm(vy)
        ez = norm(cross(ex, ey_raw))
        ey = norm(cross(ez, ex))

        # 2. Get Target Plate
        target = find_product(doc.Product, "202_LOWER PLATE")
        if not target:
            print("Target 202_LOWER PLATE not found.")
            return

        # STL calculation
        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        stl_path = os.path.join(temp_dir, f"measure_axis_{int(time.time())}.stl")
        target.ReferenceProduct.Parent.ExportData(stl_path, "stl")

        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        
        found = False
        with open(stl_path, 'r') as f:
            for line in f:
                if "vertex" in line.lower():
                    pts = line.split()
                    if len(pts) >= 4:
                        px, py, pz = float(pts[1]), float(pts[2]), float(pts[3])
                        # The part's STL is typically in its internal local coordinate system.
                        # We'll assume the part is not rotated significantly in the assembly 
                        # OR that CATIA exports it in assembly frame if we export from Product.
                        # Usually .ExportData on a Document exports in internal frame.
                        
                        dx, dy, dz = px - o[0], py - o[1], pz - o[2]
                        tx = dx*ex[0] + dy*ex[1] + dz*ex[2]
                        ty = dx*ey[0] + dy*ey[1] + dz*ey[2]
                        tz = dx*ez[0] + dy*ez[1] + dz*ez[2]
                        xmin, ymin, zmin = min(xmin, tx), min(ymin, ty), min(zmin, tz)
                        xmax, ymax, zmax = max(xmax, tx), max(ymax, ty), max(zmax, tz)
                        found = True

        if found:
            width = xmax - xmin
            depth = ymax - ymin
            height = zmax - zmin
            print(f"\nFINAL DIMENSIONS in AP_AXIS frame:")
            print(f"X: {width:.2f} mm")
            print(f"Y: {depth:.2f} mm")
            print(f"Z: {height:.2f} mm")
            
            dims = sorted([width, depth, height], reverse=True)
            print(f"Rough Stock String: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f}")
        
        if os.path.exists(stl_path): os.remove(stl_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_basis_v3()
