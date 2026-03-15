import win32com.client
import os
import math
from app.services.catia_bridge import catia_bridge

def parse_stl_bbox(filepath):
    xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
    xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
    found = False
    
    with open(filepath, 'r') as f:
        for line in f:
            if line.strip().startswith('vertex'):
                parts = line.split()
                if len(parts) >= 4:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    xmin = min(xmin, x)
                    ymin = min(ymin, y)
                    zmin = min(zmin, z)
                    
                    xmax = max(xmax, x)
                    ymax = max(ymax, y)
                    zmax = max(zmax, z)
                    found = True
                    
    if found:
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        return dx, dy, dz
    return 0, 0, 0

def test_stl_bbox():
    caa = catia_bridge.get_application()
    doc = caa.ActiveDocument
    root = doc.Product
    
    def find_prod(p, name):
        if name.upper() in p.Name.upper(): return p
        try:
            for i in range(1, p.Products.Count + 1):
                res = find_prod(p.Products.Item(i), name)
                if res: return res
        except: pass
        return None
        
    target = find_prod(root, "001_LOWER SHOE")
    if not target: return
    
    ref_doc = target.ReferenceProduct.Parent
    part_path = ref_doc.FullName
    part_doc = caa.Documents.Open(part_path)
    part = part_doc.Part
    
    print("\nAttempting STL Export technique on MainBody...")
    
    temp_stl = os.path.join(os.getcwd(), "temp_bbox_eval.stl")
    if os.path.exists(temp_stl):
        os.remove(temp_stl)
        
    new_doc = None
    try:
        sel = part_doc.Selection
        sel.Clear()
        
        sel.Add(part.MainBody)
        sel.Copy()
        sel.Clear()
        
        new_doc = caa.Documents.Add("Part")
        new_part = new_doc.Part
        
        new_sel = new_doc.Selection
        new_sel.Clear()
        new_sel.Add(new_part)
        new_sel.PasteSpecial("CATPrtResultWithOutLink")
        new_sel.Clear()
        
        new_part.Update()
        
        # Make sure document is active for export
        new_doc.ExportData(temp_stl, "stl")
        
        if os.path.exists(temp_stl):
            dx, dy, dz = parse_stl_bbox(temp_stl)
            print(f"STL Parsed BBox: {dx:.3f} x {dy:.3f} x {dz:.3f} mm")
            
            # Print sorted to compare to 1090x910x264
            dims = sorted([dx, dy, dz], reverse=True)
            print(f"Sorted Extents: {dims[0]:.3f} x {dims[1]:.3f} x {dims[2]:.3f} mm")
            
            os.remove(temp_stl)
        else:
            print("Failed to export STL.")
            
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if new_doc:
            new_doc.Close()
        part_doc.Close()

test_stl_bbox()
