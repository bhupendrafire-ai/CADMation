import win32com.client
import os
from app.services.catia_bridge import catia_bridge

def test_direct_stl_export():
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
    print(f"Opening: {part_path}")
    
    temp_stl = os.path.join(os.getcwd(), "temp_direct_export.stl")
    if os.path.exists(temp_stl):
        os.remove(temp_stl)
        
    try:
        # Open the specific part document
        part_doc = caa.Documents.Open(part_path)
        
        # Directly export the whole part to STL
        part_doc.ExportData(temp_stl, "stl")
        
        # Close the part without saving
        part_doc.Close()
        
        if os.path.exists(temp_stl):
            xmin, ymin, zmin = float('inf'), float('inf'), float('inf')
            xmax, ymax, zmax = float('-inf'), float('-inf'), float('-inf')
            found = False
            
            with open(temp_stl, 'r') as f:
                for line in f:
                    if line.strip().startswith('vertex'):
                        parts = line.split()
                        if len(parts) >= 4:
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            xmin = min(xmin, x); ymin = min(ymin, y); zmin = min(zmin, z)
                            xmax = max(xmax, x); ymax = max(ymax, y); zmax = max(zmax, z)
                            found = True
                            
            os.remove(temp_stl)
            
            if found:
                dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
                dims = sorted([dx, dy, dz], reverse=True)
                print(f"Direct STL Bounds: {dims[0]:.3f} x {dims[1]:.3f} x {dims[2]:.3f} mm")
        else:
            print("ExportData did not create the STL file.")
            
    except Exception as e:
        print(f"Failed: {e}")

test_direct_stl_export()
