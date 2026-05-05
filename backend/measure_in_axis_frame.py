import win32com.client
import sys
import os
import math

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from app.services.geometry_service import geometry_service

def get_axis_basis(axis_obj):
    try:
        o = [0.0, 0.0, 0.0]
        axis_obj.GetOrigin(o)
        vx, vy = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        axis_obj.GetVectors(vx, vy)
        
        # Orthonormalizing
        def norm(v):
            l = math.sqrt(sum(x*x for x in v))
            return [x/l for x in v] if l > 0 else None
        
        def cross(a, b):
            return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

        ex = norm(vx)
        ey_raw = norm(vy)
        ez = norm(cross(ex, ey_raw))
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
            print("Missing Axis or Part.")
            return

        print(f"Axis: {ap_axis.Name} in {adapter.Name}")
        basis = get_axis_basis(ap_axis)
        if not basis: return
        origin, ex, ey, ez = basis

        # 1. Get STL file for the target
        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        stl_path = os.path.join(temp_dir, "measure_temp.stl")
        
        # We'll use CATIA's ExportData to get the STL
        # Need to open the part document or select it.
        try:
            part_doc = target.ReferenceProduct.Parent
            part_doc.ExportData(stl_path, "stl")
        except Exception as e:
            print(f"Export failed: {e}")
            return

        # 2. Parse STL and project onto axis
        xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
        xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
        
        with open(stl_path, 'r') as f:
            for line in f:
                if "vertex" in line.lower():
                    pts = line.split()
                    if len(pts) >= 4:
                        px, py, pz = float(pts[1]), float(pts[2]), float(pts[3])
                        # Local vector from axis origin
                        dx, dy, dz = px - origin[0], py - origin[1], pz - origin[2]
                        # Project onto axis units
                        tx = dx*ex[0] + dy*ex[1] + dz*ex[2]
                        ty = dx*ey[0] + dy*ey[1] + dz*ey[2]
                        tz = dx*ez[0] + dy*ez[1] + dz*ez[2]
                        
                        xmin, ymin, zmin = min(xmin, tx), min(ymin, ty), min(zmin, tz)
                        xmax, ymax, zmax = max(xmax, tx), max(ymax, ty), max(zmax, tz)

        print(f"\nROUGH STOCK RESULTS (in AP_AXIS frame):")
        width = xmax - xmin
        depth = ymax - ymin
        height = zmax - zmin
        print(f"X (Width) : {width:.2f} mm")
        print(f"Y (Depth) : {depth:.2f} mm")
        print(f"Z (Height): {height:.2f} mm")
        
        # Sort dimensions as Rough Stock usually does
        dims = sorted([width, depth, height], reverse=True)
        print(f"Size String: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f}")

        if os.path.exists(stl_path): os.remove(stl_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_in_axis()
