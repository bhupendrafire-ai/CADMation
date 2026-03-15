import logging
import sys
import os

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge

logging.basicConfig(level=logging.INFO)

def test_drawing_bbox():
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
    print(f"\n--- Drawing BBox Test for {target_prod.Name} ---")
    
    # 1. Open parts Reference document
    part_doc = target_prod.ReferenceProduct.Parent
    
    # 2. Add temporary Drawing
    draw_doc = caa.Documents.Add("Drawing")
    sheets = draw_doc.Sheets
    sheet = sheets.ActiveSheet
    views = sheet.Views
    
    # 3. Create Top View
    top_view = views.Add("AutomaticNaming")
    generative_top = top_view.GenerativeBehavior
    generative_top.Document = target_prod.ReferenceProduct
    generative_top.DefineFrontView(0, 1, 0, 1, 0, 0)
    generative_top.Update()
    
    top_bbox = [0.0] * 4
    try:
        # XMin, YMin, XMax, YMax
        res = top_view.Size(top_bbox)
        if isinstance(res, tuple): top_bbox = res
        dx = abs(top_bbox[2] - top_bbox[0])
        dy = abs(top_bbox[3] - top_bbox[1])
        print(f"Top View Bounds: {dx:.2f} x {dy:.2f}")
    except Exception as e:
        print(f"Failed to get Top View bounds: {e}")
        
    # 4. Create Front View
    front_view = views.Add("AutomaticNaming")
    generative_front = front_view.GenerativeBehavior
    generative_front.Document = target_prod.ReferenceProduct
    generative_front.DefineFrontView(0, 0, 1, 1, 0, 0)
    generative_front.Update()
    
    front_bbox = [0.0] * 4
    try:
        res = front_view.Size(front_bbox)
        if isinstance(res, tuple): front_bbox = res
        dz = abs(front_bbox[3] - front_bbox[1])
        print(f"Front View Depth: {dz:.2f}")
    except Exception as e:
        print(f"Failed to get Front View bounds: {e}")

    # Close temporary drawing without saving
    caa.DisplayFileAlerts = False
    draw_doc.Close()
    caa.DisplayFileAlerts = True

if __name__ == "__main__":
    test_drawing_bbox()
