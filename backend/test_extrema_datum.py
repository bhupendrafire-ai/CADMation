import win32com.client
from app.services.catia_bridge import catia_bridge

def extract_extrema_datum():
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
    
    factory = part.HybridShapeFactory
    
    print("\nAttempting Datum Extrema measurement on MainBody...")
    
    try:
        main_body_ref = part.CreateReferenceFromObject(part.MainBody)
        
        dirX = factory.AddNewDirectionByCoord(1, 0, 0)
        dirY = factory.AddNewDirectionByCoord(0, 1, 0)
        dirZ = factory.AddNewDirectionByCoord(0, 0, 1)
        
        exts = [
            factory.AddNewExtremum(main_body_ref, dirX, 1),
            factory.AddNewExtremum(main_body_ref, dirX, 0),
            factory.AddNewExtremum(main_body_ref, dirY, 1),
            factory.AddNewExtremum(main_body_ref, dirY, 0),
            factory.AddNewExtremum(main_body_ref, dirZ, 1),
            factory.AddNewExtremum(main_body_ref, dirZ, 0)
        ]
        
        hb = part.HybridBodies.Add()
        hb.Name = "TEMP_BBOX_EXTREMA"
        
        datums = []
        for e in exts:
            hb.AppendHybridShape(e)
            part.UpdateObject(e)
            
            # Isolate
            ref_e = part.CreateReferenceFromObject(e)
            datum = factory.AddNewPointDatum(ref_e)
            hb.AppendHybridShape(datum)
            part.UpdateObject(datum)
            datums.append(datum)
        
        coords = []
        for d in datums:
            # GetCoordinates requires an array setup
            try:
                c = [0.0, 0.0, 0.0]
                d.GetCoordinates(c)
                coords.append(c)
                print(f"Point: {c}")
            except Exception as pe:
                print(f"GetCoordinates failed: {pe}, trying script...")
                import pythoncom
                script = f"""
                Function CATMain(p)
                    Dim c(2)
                    p.GetCoordinates c
                    CATMain = c(0) & "|" & c(1) & "|" & c(2)
                End Function
                """
                try:
                    res = caa.SystemService.Evaluate(script, 1, "CATMain", [d])
                    parts = res.split('|')
                    coords.append([float(parts[0]), float(parts[1]), float(parts[2])])
                    print(f"Point via Script: {coords[-1]}")
                except Exception as se:
                    print(f"Script evaluate failed: {se}")
                    coords.append([0.0, 0.0, 0.0])
                
        # Cleanup
        part_doc.Selection.Clear()
        part_doc.Selection.Add(hb)
        part_doc.Selection.Delete()
        part_doc.Selection.Clear()
        
        if len(coords) == 6:
            dx = abs(coords[0][0] - coords[1][0])
            dy = abs(coords[2][1] - coords[3][1])
            dz = abs(coords[4][2] - coords[5][2])
            print(f"Exact Extrema Size: {dx:.3f} x {dy:.3f} x {dz:.3f} mm")
            
    except Exception as e:
        print(f"Outer Failed: {e}")
        
    part_doc.Close()

extract_extrema_datum()
