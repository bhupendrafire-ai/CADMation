import logging
import sys
import os
import math

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

def test_transformation():
    target_name = "001_LOWER SHOE"
    caa = catia_bridge.get_application()
    if not caa: return
    
    doc = caa.ActiveDocument
    root = doc.Product
    
    def find_prod(p, name):
        if name.upper() in p.Name.upper(): return p
        for i in range(1, p.Products.Count + 1):
            res = find_prod(p.Products.Item(i), name)
            if res: return res
        return None
        
    target = find_prod(root, target_name)
    if not target: return
    
    print(f"Target: {target.Name}")
    
    # Get Transformation
    matrix = [0.0]*12
    target.Position.GetComponents(matrix)
    print(f"Matrix: {matrix}")
    
    # Transformation math:
    # x_global = R1*x_local + R2*y_local + R3*z_local + Tx
    # y_global = R4*x_local + R5*y_local + R6*z_local + Ty
    # z_global = R7*x_local + R8*y_local + R9*z_local + Tz
    # Matrix components from GetComponents are [R1, R2, R3, R4, R5, R6, R7, R8, R9, Tx, Ty, Tz]
    
    def transform(pt, m):
        x, y, z = pt
        xg = m[0]*x + m[1]*y + m[2]*z + m[9]
        yg = m[3]*x + m[4]*y + m[5]*z + m[10]
        zg = m[6]*x + m[7]*y + m[8]*z + m[11]
        return (xg, yg, zg)

    # Get Local BBox of MainBody
    try:
        ref_doc = target.ReferenceProduct.Parent
        part = ref_doc.Part
        spa = ref_doc.GetWorkbench("SPAWorkbench")
        body = part.MainBody
        m = spa.GetMeasurable(body)
        bbox = [0.0]*6
        m.GetBoundaryBox(bbox)
        
        # Local min/max
        local_pts = [
            (bbox[0], bbox[1], bbox[2]), # min min min
            (bbox[3], bbox[1], bbox[2]), # max min min
            (bbox[0], bbox[4], bbox[2]),
            (bbox[3], bbox[4], bbox[2]),
            (bbox[0], bbox[1], bbox[5]),
            (bbox[3], bbox[1], bbox[5]),
            (bbox[0], bbox[4], bbox[5]),
            (bbox[3], bbox[4], bbox[5]), # max max max
        ]
        
        global_min = [float('inf')] * 3
        global_max = [float('-inf')] * 3
        
        for pt in local_pts:
            gx, gy, gz = transform(pt, matrix)
            global_min[0] = min(global_min[0], gx)
            global_min[1] = min(global_min[1], gy)
            global_min[2] = min(global_min[2], gz)
            global_max[0] = max(global_max[0], gx)
            global_max[1] = max(global_max[1], gy)
            global_max[2] = max(global_max[2], gz)
            
        dx = (global_max[0] - global_min[0]) * 1000
        dy = (global_max[1] - global_min[1]) * 1000
        dz = (global_max[2] - global_min[2]) * 1000
        print(f"TRANSFORMED GLOBAL BBOX: {dx:.1f} x {dy:.1f} x {dz:.1f} mm")
        
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_transformation()
