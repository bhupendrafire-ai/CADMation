import win32com.client
from app.services.catia_bridge import catia_bridge

def vba_measure_eval_main():
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
        
        Dim pDoc As Document
        Set pDoc = target.ReferenceProduct.Parent
        Dim p As Part
        Set p = pDoc.Part
        Dim spa
        Set spa = pDoc.GetWorkbench("SPAWorkbench")
        
        outStr = "MainBody: " & p.MainBody.Name & vbCrLf
        
        Dim m, bbox(5), dx, dy, dz
        
        Err.Clear
        Set m = spa.GetMeasurable(p.MainBody)
        If Err.Number <> 0 Then
            outStr = outStr & "GetMeasurable failed: " & Err.Description & vbCrLf
        Else
            m.GetBoundaryBox bbox
            If Err.Number <> 0 Then
                outStr = outStr & "GetBoundaryBox failed: " & Err.Description & vbCrLf
            Else
                dx = Abs(bbox(3) - bbox(0)) * 1000
                dy = Abs(bbox(4) - bbox(1)) * 1000
                dz = Abs(bbox(5) - bbox(2)) * 1000
                outStr = outStr & "Size: " & CStr(Round(dx,1)) & " x " & CStr(Round(dy,1)) & " x " & CStr(Round(dz,1)) & vbCrLf
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

vba_measure_eval_main()
