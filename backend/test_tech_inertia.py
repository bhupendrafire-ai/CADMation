import win32com.client
from app.services.catia_bridge import catia_bridge

def test_tech_inertia():
    caa = catia_bridge.get_application()
    
    script = """
    Function CATMain()
        Dim outStr
        outStr = ""
        On Error Resume Next
        
        Dim doc As Document
        Set doc = CATIA.ActiveDocument
        Dim root As Product
        Set root = doc.Product
        
        Dim target As Product
        Set target = FindTarget(root, "001_LOWER SHOE")
        If target Is Nothing Then
            CATMain = "Not found"
            Exit Function
        End If
        
        Dim inertia
        Err.Clear
        Set inertia = target.GetTechnologicalObject("Inertia")
        If Err.Number <> 0 Then
            outStr = "GetTechnologicalObject('Inertia') failed: " & Err.Description
        Else
            Dim mass
            mass = inertia.Mass
            outStr = "Mass: " & CStr(mass) & " kg" & vbCrLf
            
            Dim b(8)
            inertia.GetPrincipalAxes b
            outStr = outStr & "Principal Axes: " & CStr(b(0)) & ", " & CStr(b(1)) & ", " & CStr(b(2)) & vbCrLf
            
            ' Try bounding box? Inertia object might have it
            Dim bbox(5), dx, dy, dz
            Err.Clear
            inertia.GetBoundingBox bbox
            If Err.Number <> 0 Then
                outStr = outStr & "GetBoundingBox failed on Inertia: " & Err.Description
            Else
                dx = Abs(bbox(3) - bbox(0)) * 1000
                dy = Abs(bbox(4) - bbox(1)) * 1000
                dz = Abs(bbox(5) - bbox(2)) * 1000
                outStr = outStr & "Size: " & CStr(Round(dx,1)) & " x " & CStr(Round(dy,1)) & " x " & CStr(Round(dz,1))
            End If
        End If
        
        CATMain = outStr
    End Function

    Function FindTarget(pProd, name)
        Dim i, child, res
        If InStr(UCase(pProd.Name), UCase(name)) > 0 Then
            Set FindTarget = pProd
            Exit Function
        End If
        For i = 1 To pProd.Products.Count
            Set child = pProd.Products.Item(i)
            Set res = FindTarget(child, name)
            If Not res Is Nothing Then
                Set FindTarget = res
                Exit Function
            End If
        Next
        Set FindTarget = Nothing
    End Function
    """
    
    try:
        res = caa.SystemService.Evaluate(script, 1, "CATMain", []) # 1 = CATScriptLanguage
        print(f"Result:\n{res}")
    except Exception as e:
        print(f"Failed: {e}")

test_tech_inertia()
