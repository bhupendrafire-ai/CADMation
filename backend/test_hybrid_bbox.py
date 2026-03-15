import logging
import sys
import os
import math

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

logging.basicConfig(level=logging.INFO)

def test_geom_bbox():
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
        return
        
    part = target_prod.ReferenceProduct.Parent.Part
    print(f"\n--- Coordinate BBox Test for {target_prod.Name} ---")
    
    # Let's try to get absolute points of the solid
    # We can create an extremity point
    try:
        hsf = part.HybridShapeFactory
        body = part.MainBody
        
        # We need a reference to the solid
        ref_body = part.CreateReferenceFromObject(body)
        
        # create extremum in X
        dir_x = hsf.AddNewDirectionByCoord(1, 0, 0)
        ext_x_max = hsf.AddNewExtremum(ref_body, dir_x, 1)
        ext_x_min = hsf.AddNewExtremum(ref_body, dir_x, 0)
        
        dir_y = hsf.AddNewDirectionByCoord(0, 1, 0)
        ext_y_max = hsf.AddNewExtremum(ref_body, dir_y, 1)
        ext_y_min = hsf.AddNewExtremum(ref_body, dir_y, 0)
        
        dir_z = hsf.AddNewDirectionByCoord(0, 0, 1)
        ext_z_max = hsf.AddNewExtremum(ref_body, dir_z, 1)
        ext_z_min = hsf.AddNewExtremum(ref_body, dir_z, 0)
        
        # Evaluate
        spa = part.Parent.GetWorkbench("SPAWorkbench")
        
        def get_dist(ext1, ext2):
            m1 = spa.GetMeasurable(part.CreateReferenceFromObject(ext1))
            m2 = spa.GetMeasurable(part.CreateReferenceFromObject(ext2))
            # Just get coords
            coord1 = [0.0, 0.0, 0.0]
            coord2 = [0.0, 0.0, 0.0]
            
            # Since Extremums are endpoints, let's use the old standard
            doc.Selection.Clear()
            doc.Selection.Add(ext1)
            # Actually, SPA GetMeasurable.GetPoint is best
            res1 = m1.GetPoint(coord1)
            if isinstance(res1, tuple): coord1 = res1
            res2 = m2.GetPoint(coord2)
            if isinstance(res2, tuple): coord2 = res2
            
            return math.sqrt((coord1[0]-coord2[0])**2 + (coord1[1]-coord2[1])**2 + (coord1[2]-coord2[2])**2) * 1000
            
        dx = get_dist(ext_x_max, ext_x_min)
        dy = get_dist(ext_y_max, ext_y_min)
        dz = get_dist(ext_z_max, ext_z_min)
        
        print(f"HybridShapeFactory Extremum: {dx:.2f} x {dy:.2f} x {dz:.2f}")

    except Exception as e:
        print(f"HSF failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_geom_bbox()
