import sys
from app.services.catia_bridge import catia_bridge

def main():
    caa = catia_bridge.get_application()
    if not caa:
        print("CATIA not connected.")
        return
        
    script = """
    Function CATMain()
        Dim outStr
        outStr = ""
        On Error Resume Next
        
        Dim doc As Document
        Set doc = CATIA.ActiveDocument
        
        Dim target As Product
        Dim i
        
        ' Find target doc
        Dim targetDoc
        Set targetDoc = Nothing
        For i = 1 To CATIA.Documents.Count
            If InStr(CATIA.Documents.Item(i).Name, "203_UPPER") > 0 Then
                Set targetDoc = CATIA.Documents.Item(i)
                Exit For
            End If
        Next
        
        If targetDoc Is Nothing Then
            CATMain = "Not found"
            Exit Function
        End If
        
        Set target = targetDoc.Product
        
        Dim inertia
        Err.Clear
        Set inertia = target.GetTechnologicalObject("Inertia")
        If Err.Number <> 0 Then
            outStr = "GetTechnologicalObject('Inertia') failed: " & Err.Description
        Else
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
    """
    
    try:
        res = caa.SystemService.Evaluate(script, 1, "CATMain", [])
        print(f"Result:\n{res}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
