import win32com.client
from app.services.catia_bridge import catia_bridge

def test_catscript():
    caa = catia_bridge.get_application()
    
    script = """
    Function CATMain()
        Set doc = CATIA.ActiveDocument
        Set root = doc.Product
        
        Dim target As Product
        Set target = Nothing
        
        For i = 1 To root.Products.Count
            If InStr(UCase(root.Products.Item(i).Name), "001_LOWER SHOE") > 0 Then
                Set target = root.Products.Item(i)
                Exit For
            End If
        Next
        
        If target Is Nothing Then
            CATMain = "Target not found"
            Exit Function
        End If
        
        Dim partDoc As Document
        Set partDoc = target.ReferenceProduct.Parent
        
        Dim p As Part
        Set p = partDoc.Part
        
        Dim spa
        Set spa = partDoc.GetWorkbench("SPAWorkbench")
        
        Dim m
        Set m = spa.GetMeasurable(p.MainBody)
        
        Dim b(5)
        m.GetBoundaryBox b
        
        Dim dx, dy, dz
        dx = Abs(b(3) - b(0)) * 1000
        dy = Abs(b(4) - b(1)) * 1000
        dz = Abs(b(5) - b(2)) * 1000
        
        CATMain = "MainBody: " & dx & " x " & dy & " x " & dz
    End Function
    """
    
    try:
        res = caa.SystemService.Evaluate(script, 1, "CATMain", []) # 1 = CATScriptLanguage
        print(f"CATScript Result: {res}")
    except Exception as e:
        print(f"CATScript failed: {e}")

test_catscript()
