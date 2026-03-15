import win32com.client
import pythoncom
import math

def research():
    try:
        caa = win32com.client.Dispatch("CATIA.Application")
        
        part_doc = None
        for i in range(1, caa.Documents.Count + 1):
            d = caa.Documents.Item(i)
            if ".CATPart" in d.Name:
                part_doc = d
                break
        
        if not part_doc:
            print("No CATPart found open.")
            return

        doc = part_doc
        part = doc.Part
        print(f"Testing Part: {doc.Name}")
        
        spa = doc.GetWorkbench("SPAWorkbench")
        
        # Iterate all bodies to find the "Main" one or combine them
        bodies = part.Bodies
        for i in range(1, bodies.Count + 1):
            body = bodies.Item(i)
            print(f"\nProcessing Body: {body.Name}")
            
            try:
                ref = part.CreateReferenceFromObject(body)
                meas = spa.GetMeasurable(ref)
                
                # 1. GetBoundaryBox (AABB)
                # In Python win32com, Out parameters are returned as a tuple
                try:
                    # GetBoundaryBox typically takes 6 doubles
                    # We might need to pass a list or it returns a tuple
                    dummy = [0.0] * 6
                    bbox_aabb = meas.GetBoundaryBox(dummy)
                    # If it returns a tuple, we use it
                    if isinstance(bbox_aabb, tuple) or isinstance(bbox_aabb, list):
                        pass
                    else:
                        bbox_aabb = dummy
                        
                    l_aabb = abs(bbox_aabb[3] - bbox_aabb[0]) * 1000
                    w_aabb = abs(bbox_aabb[4] - bbox_aabb[1]) * 1000
                    h_aabb = abs(bbox_aabb[5] - bbox_aabb[2]) * 1000
                    print(f"  AABB (mm): L={l_aabb:.1f}, W={w_aabb:.1f}, H={h_aabb:.1f}")
                except Exception as e:
                    print(f"  AABB Failed: {e}")

                # 2. GetMinimumBoundingBox (OOBB)
                try:
                    dummy2 = [0.0] * 9
                    bbox_oobb = meas.GetMinimumBoundingBox(dummy2)
                    
                    # Usually GetMinimumBoundingBox returns the tightest fit.
                    # The dimensions are extracted between points in the 9-array.
                    # Standard CATIA documentation says:
                    # Point 1 (0,1,2), Point 2 (3,4,5), Point 3 (6,7,8) ?
                    # NO, for GetMinimumBoundingBox on a solid, it returns 9 values.
                    # Often it's MinX, MinY, MinZ, MaxX, MaxY, MaxZ, ...
                    
                    if not bbox_oobb: bbox_oobb = dummy2
                    
                    l_oobb = abs(bbox_oobb[3] - bbox_oobb[0]) * 1000
                    w_oobb = abs(bbox_oobb[4] - bbox_oobb[1]) * 1000
                    h_oobb = abs(bbox_oobb[5] - bbox_oobb[2]) * 1000
                    print(f"  OOBB (mm): L={l_oobb:.1f}, W={w_oobb:.1f}, H={h_oobb:.1f}")
                except Exception as e:
                    print(f"  OOBB Failed: {e}")

            except Exception as e:
                print(f"  Body processing failed: {e}")

    except Exception as e:
        print(f"Outer Error: {e}")

if __name__ == "__main__":
    research()
