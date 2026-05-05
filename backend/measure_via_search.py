import win32com.client
import sys
import os
import math
import time

def measure_via_search():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        print(f"Searching for AP_AXIS...")
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        if sel.Count == 0:
            print("AP_AXIS not found via Search.")
            # Try partial
            sel.Search("Name='*AP_AXIS*',all")
        
        if sel.Count == 0:
            print("AP_AXIS still not found.")
            return
            
        axis_obj = sel.Item(1).Value
        print(f"Axis found: {axis_obj.Name}")
        
        print("Searching for 202_LOWER PLATE...")
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        if sel.Count == 0:
            print("202_LOWER PLATE not found.")
            return
        
        plate_obj = sel.Item(1).Value
        print(f"Plate found: {plate_obj.Name}")
        
        # Now get dimensions
        # 1. STL Method result (already known, but we re-verify if needed)
        # 2. Bounding Box in Axis Frame
        
        # Extract basis from axis_obj
        o = [0.0, 0.0, 0.0]
        vx = [0.0, 0.0, 0.0]
        vy = [0.0, 0.0, 0.0]
        
        # Try getting vectors
        try:
            axis_obj.GetOrigin(o)
            axis_obj.GetVectors(vx, vy)
        except Exception as e:
            print(f"GetOrigin/Vectors failed: {e}")
            # Fallback to absolute if vectors are 0
            vx, vy = [1,0,0], [0,1,0]

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

        # Export STL
        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        stl_path = os.path.join(temp_dir, "final_search_measure.stl")
        
        # Find the document for the plate
        # If plate_obj is a Product, get its ReferenceProduct.Parent (Document)
        try:
            doc_to_export = None
            if hasattr(plate_obj, "ReferenceProduct"):
                doc_to_export = plate_obj.ReferenceProduct.Parent
            else:
                doc_to_export = plate_obj.Parent
                while not hasattr(doc_to_export, "ExportData"):
                    doc_to_export = doc_to_export.Parent
            
            doc_to_export.ExportData(stl_path, "stl")
        except Exception as e:
            print(f"Export failed: {e}")
            return

        # Calculate BB in axis
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
        
        print("\nRESULTS:")
        print(f"X: {width:.2f} mm")
        print(f"Y: {depth:.2f} mm")
        print(f"Z: {height:.2f} mm")
        
        dims = sorted([width, depth, height], reverse=True)
        print(f"Rough Stock: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f}")

        if os.path.exists(stl_path): os.remove(stl_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_via_search()
