import win32com.client
import pythoncom
import math

def test_measurable():
    try:
        caa = win32com.client.Dispatch("CATIA.Application")
        # Find a CATPart
        part_doc = None
        for i in range(1, caa.Documents.Count + 1):
            d = caa.Documents.Item(i)
            if ".CATPart" in d.Name:
                part_doc = d
                break
        
        if not part_doc:
            print("No CATPart found.")
            return

        print(f"Testing Part: {part_doc.Name}")
        part = part_doc.Part
        
        spa = part_doc.GetWorkbench("SPAWorkbench")
        ref = part.CreateReferenceFromObject(part.MainBody)
        meas = spa.GetMeasurable(ref)
        
        # Test 2: GetMinimumBoundingBox
        print("Calling GetMinimumBoundingBox...")
        dummy = [0.0] * 9
        try:
            # In win32com, out parameters are usually returned as a tuple
            # The input array might be ignored
            res = meas.GetMinimumBoundingBox(dummy)
            print(f"Result Type: {type(res)}")
            print(f"Result Value: {res}")
            
            if isinstance(res, tuple) and len(res) >= 6:
                p1 = (res[0], res[1], res[2])
                p2 = (res[3], res[4], res[5])
                p3 = (res[6], res[7], res[8])
                
                d12 = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2 + (p2[2]-p1[2])**2) * 1000
                d13 = math.sqrt((p3[0]-p1[0])**2 + (p3[1]-p1[1])**2 + (p3[2]-p1[2])**2) * 1000
                print(f"Dim 1: {d12:.1f} mm")
                print(f"Dim 2: {d13:.1f} mm")
        except Exception as e:
            print(f"GetMinimumBoundingBox Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_measurable()
