import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

logging.basicConfig(level=logging.INFO)

def test_precise_bbox():
    target_name = "203_UPPER_FLANGE_STEEL_01.1"
    
    caa = catia_bridge.get_application()
    if not caa: return
        
    doc = caa.ActiveDocument
    
    def find_target(prod):
        if target_name in prod.Name:
            return prod
        for i in range(1, prod.Products.Count + 1):
            res = find_target(prod.Products.Item(i))
            if res: return res
        return None

    target_prod = find_target(doc.Product)
    if not target_prod:
        print(f"Could not find {target_name}")
        return
        
    part = target_prod.ReferenceProduct.Parent.Part
    print(f"\n--- Precise BBox Test for {target_prod.Name} ---")
    
    # 1. Test SPAWorkbench OOBB
    try:
        spa = part.Parent.GetWorkbench("SPAWorkbench")
        measurable = spa.GetMeasurable(part.MainBody)
        
        # AABB
        bbox_aabb = [0.0]*6
        res_aabb = measurable.GetBoundaryBox(bbox_aabb)
        if isinstance(res_aabb, tuple): bbox_aabb = res_aabb
        dx = abs(bbox_aabb[3]-bbox_aabb[0]) * 1000
        dy = abs(bbox_aabb[4]-bbox_aabb[1]) * 1000
        dz = abs(bbox_aabb[5]-bbox_aabb[2]) * 1000
        print(f"AABB: {dx:.2f} x {dy:.2f} x {dz:.2f}")
        
        # OOBB
        bbox_oobb = [0.0]*9
        res_oobb = measurable.GetMinimumBoundingBox(bbox_oobb)
        if isinstance(res_oobb, tuple): bbox_oobb = res_oobb
        
        import math
        p1 = (bbox_oobb[0], bbox_oobb[1], bbox_oobb[2])
        p2 = (bbox_oobb[3], bbox_oobb[4], bbox_oobb[5])
        p3 = (bbox_oobb[6], bbox_oobb[7], bbox_oobb[8])
        
        d12 = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2 + (p2[2]-p1[2])**2) * 1000
        d13 = math.sqrt((p3[0]-p1[0])**2 + (p3[1]-p1[1])**2 + (p3[2]-p1[2])**2) * 1000
        
        # Try to calculate depth from Volume
        vol = target_prod.ReferenceProduct.Analyze.Volume * 1e9
        d3 = vol / (d12 * d13) if (d12 > 0 and d13 > 0) else 0

        oobb_dims = sorted([d12, d13, d3], reverse=True)
        print(f"OOBB (Calc Depth): {oobb_dims[0]:.2f} x {oobb_dims[1]:.2f} x {oobb_dims[2]:.2f}")
    except Exception as e:
        print(f"SPAWorkbench failed: {e}")

    # 2. Part Infrastructure BBox (Inertia)
    try:
        inertia = spa.GetMeasurable(part.MainBody)
        # Not natively exposed via COM directly for dimensions without macros,
        # but the AABB should give us the absolute extremes in standard orientation.
    except Exception as e:
        print(f"Inertia failed: {e}")

if __name__ == "__main__":
    test_precise_bbox()
