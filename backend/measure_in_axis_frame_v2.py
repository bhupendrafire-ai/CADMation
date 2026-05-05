import win32com.client
import sys
import os
import math

def get_axis_basis(axis_obj):
    try:
        o = [0.0, 0.0, 0.0]
        axis_obj.GetOrigin(o)
        
        vx = [0.0, 0.0, 0.0]
        vy = [0.0, 0.0, 0.0]
        
        success = False
        try:
            axis_obj.GetVectors(vx, vy)
            success = True
        except:
            try:
                axis_obj.XAxis.GetDirection(vx)
                axis_obj.YAxis.GetDirection(vy)
                success = True
            except: pass
            
        if not success:
            print("Could not retrieve vectors from axis system.")
            return None
        
        def norm(v):
            l = math.sqrt(sum(x*x for x in v))
            return [x/l for x in v] if l > 0 else None
        
        def cross(a, b):
            return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

        ex = norm(vx)
        ey_raw = norm(vy)
        if not ex or not ey_raw: return None
        
        ez = norm(cross(ex, ey_raw))
        if not ez: return None
        ey = norm(cross(ez, ex))
        
        return o, ex, ey, ez
    except Exception as e:
        print(f"Error reading axis basis: {e}")
        return None

def measure_in_axis():
    try:
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

        adapter = find_product(doc.Product, "ADAPTER_LOWER_AND_UPPER_DIE")
        target = find_product(doc.Product, "202_LOWER PLATE")
        
        ap_axis = None
        if adapter:
            try:
                part = adapter.ReferenceProduct.Parent.Part
                for i in range(1, part.AxisSystems.Count + 1):
                    ax = part.AxisSystems.Item(i)
                    if "AP_AXIS" in ax.Name.upper():
                        ap_axis = ax
                        break
            except: pass

        if not ap_axis or not target:
            print(f"Error: AP_AXIS found? {ap_axis is not None}, Target found? {target is not None}")
            return

        print(f"Axis: {ap_axis.Name}")
        basis = get_axis_basis(ap_axis)
        if not basis: 
            print("Failed to get basis.")
            return
        origin, ex, ey, ez = basis

        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        stl_path = os.path.join(temp_dir, f"measure_axis_{int(time.time())}.stl")
        
        try:
            part_doc = target.ReferenceProduct.Parent
            part_doc.ExportData(stl_path, "stl")
        except Exception as e:
            print(f"Export failed: {e}")
            return

        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        
        found = False
        with open(stl_path, 'r') as f:
            for line in f:
                if "vertex" in line.lower():
                    pts = line.split()
                    if len(pts) >= 4:
                        px, py, pz = float(pts[1]), float(pts[2]), float(pts[3])
                        dx, dy, dz = px - origin[0], py - origin[1], pz - origin[2]
                        tx = dx*ex[0] + dy*ex[1] + dz*ex[2]
                        ty = dx*ey[0] + dy*ey[1] + dz*ey[2]
                        tz = dx*ez[0] + dy*ez[1] + dz*ez[2]
                        xmin, ymin, zmin = min(xmin, tx), min(ymin, ty), min(zmin, tz)
                        xmax, ymax, zmax = max(xmax, tx), max(ymax, ty), max(zmax, tz)
                        found = True

        if not found:
            print("No vertices found in STL.")
            return

        width = xmax - xmin
        depth = ymax - ymin
        height = zmax - zmin

        print(f"\nROUGH STOCK RESULTS (in AP_AXIS frame):")
        print(f"X (Width) : {width:.2f} mm")
        print(f"Y (Depth) : {depth:.2f} mm")
        print(f"Z (Height): {height:.2f} mm")
        
        dims = sorted([width, depth, height], reverse=True)
        print(f"Final Size: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f}")

        if os.path.exists(stl_path): os.remove(stl_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import time
    measure_in_axis()
