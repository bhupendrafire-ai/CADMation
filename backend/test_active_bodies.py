import win32com.client
from app.services.catia_bridge import catia_bridge

def test():
    caa = catia_bridge.get_application()
    doc = caa.ActiveDocument
    print(f"Active Document: {doc.Name}")
    
    # Is it a part or product?
    try:
        part = doc.Part
        print("Document is a Part.")
        
        spa = doc.GetWorkbench("SPAWorkbench")
        
        for i in range(1, part.Bodies.Count + 1):
            body = part.Bodies.Item(i)
            print(f"Body: {body.Name}")
            try:
                m = spa.GetMeasurable(body)
                b = [0.0]*6
                m.GetBoundaryBox(b)
                dx = abs(b[3]-b[0])*1000
                dy = abs(b[4]-b[1])*1000
                dz = abs(b[5]-b[2])*1000
                print(f"  AABB: {dx:.1f} x {dy:.1f} x {dz:.1f}")
            except Exception as e:
                print(f"  Fail: {e}")
    except:
        print("Document is NOT a Part.")
        
test()
