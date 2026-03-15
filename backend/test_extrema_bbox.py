import win32com.client
from app.services.catia_bridge import catia_bridge

def extract_extrema_dims():
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
    
    # Needs to be a HybridShapeFactory
    factory = part.HybridShapeFactory
    
    print("\nAttempting exact Extrema measurement on MainBody...")
    
    try:
        main_body_ref = part.CreateReferenceFromObject(part.MainBody)
        
        # Directions
        dirX = factory.AddNewDirectionByCoord(1, 0, 0)
        dirY = factory.AddNewDirectionByCoord(0, 1, 0)
        dirZ = factory.AddNewDirectionByCoord(0, 0, 1)
        
        extrema = []
        # Max X, Min X
        extrema.append(factory.AddNewExtremum(main_body_ref, dirX, 1)) # 1 = max, 0 = min
        extrema.append(factory.AddNewExtremum(main_body_ref, dirX, 0))
        # Max Y, Min Y
        extrema.append(factory.AddNewExtremum(main_body_ref, dirY, 1))
        extrema.append(factory.AddNewExtremum(main_body_ref, dirY, 0))
        # Max Z, Min Z
        extrema.append(factory.AddNewExtremum(main_body_ref, dirZ, 1))
        extrema.append(factory.AddNewExtremum(main_body_ref, dirZ, 0))
        
        # We need to evaluate them. We can stick them in a temporary Geometrical Set
        hb = part.HybridBodies.Add()
        hb.Name = "TEMP_BBOX_EXTREMA"
        
        for e in extrema:
            hb.AppendHybridShape(e)
            
        part.UpdateObject(hb)
        
        spa = part_doc.GetWorkbench("SPAWorkbench")
        
        coords = []
        for e in extrema:
            ref = part.CreateReferenceFromObject(e)
            m = spa.GetMeasurable(ref)
            try:
                pt = [0.0, 0.0, 0.0]
                m.GetPoint(pt)
                coords.append(pt)
            except Exception as me:
                print(f"Failed to get point: {me}")
                coords.append([0.0, 0.0, 0.0])
                
        # Cleanup
        part_doc.Selection.Clear()
        part_doc.Selection.Add(hb)
        part_doc.Selection.Delete()
        part_doc.Selection.Clear()
        
        # Calculate sizes
        print("Coords generated.")
        if len(coords) == 6:
            dx = abs(coords[0][0] - coords[1][0])
            dy = abs(coords[2][1] - coords[3][1])
            dz = abs(coords[4][2] - coords[5][2])
            print(f"Extrema Size: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
            
    except Exception as e:
        print(f"Failed: {e}")
        
    part_doc.Close()

extract_extrema_dims()
