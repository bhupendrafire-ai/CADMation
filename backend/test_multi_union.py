import win32com.client
import os
import sys

# Add the app directory to path to import services
sys.path.append(os.getcwd())

def test_multi_union():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        main_doc = caa.ActiveDocument
        target_name = "NE152000C001"
        def find_product(parent, name):
            for i in range(1, parent.Products.Count + 1):
                child = parent.Products.Item(i)
                if name.lower() in child.Name.lower() or name.lower() in child.PartNumber.lower(): return child
                res = find_product(child, name)
                if res: return res
            return None
        target = find_product(main_doc.Product, target_name)
        if not target: return print("Target not found")
        
        part = target.ReferenceProduct.Parent.Part
        spa = main_doc.GetWorkbench("SPAWorkbench")

        print(f"Bodies Count: {part.Bodies.Count}")
        print(f"HybridBodies Count: {part.HybridBodies.Count}")
        
        all_refs = []
        # 1. Standard Bodies
        for i in range(1, part.Bodies.Count + 1):
             body = part.Bodies.Item(i)
             all_refs.append(part.CreateReferenceFromObject(body))
             print(f" Added Body: {body.Name}")
             # Check Shapes inside Body
             try:
                 for j in range(1, body.Shapes.Count + 1):
                     shape = body.Shapes.Item(j)
                     all_refs.append(part.CreateReferenceFromObject(shape))
                     print(f"  Added Shape: {shape.Name}")
             except: pass
             
        # 2. HybridBodies (Geometrical Sets)
        for i in range(1, part.HybridBodies.Count + 1):
             hb = part.HybridBodies.Item(i)
             all_refs.append(part.CreateReferenceFromObject(hb))
             print(f" Added HybridBody: {hb.Name}")
             # Also try every single shape inside
             for j in range(1, hb.HybridShapes.Count + 1):
                  hs = hb.HybridShapes.Item(j)
                  all_refs.append(part.CreateReferenceFromObject(hs))
                  print(f"  Added HybridShape: {hs.Name}")

        final_bbox = [999999.0, 999999.0, 999999.0, -999999.0, -999999.0, -999999.0]
        found_any = False

        for ref in all_refs:
            try:
                # Get the object's name and type for debugging
                try:
                    obj = ref.DisplayName
                    print(f" Checking Ref: {obj}")
                except:
                    print(f" Checking Unnamed Ref")

                # Try Measurable
                try:
                    m = spa.GetMeasurable(ref)
                    temp = [0.0]*6
                    m.GetBoundaryBox(temp)
                    if any(v != 0 for v in temp):
                        print(f"  Measurable Success: {temp}")
                        found_any = True
                        final_bbox[0] = min(final_bbox[0], temp[0], temp[3])
                        final_bbox[1] = min(final_bbox[1], temp[1], temp[4])
                        final_bbox[2] = min(final_bbox[2], temp[2], temp[5])
                        final_bbox[3] = max(final_bbox[3], temp[0], temp[3])
                        final_bbox[4] = max(final_bbox[4], temp[1], temp[4])
                        final_bbox[5] = max(final_bbox[5], temp[2], temp[5])
                except Exception as e:
                    print(f"  Measurable Error: {e}")

                # Try Inertia
                try:
                    inertia = spa.GetInertia(ref)
                    temp = [0.0]*6
                    inertia.GetBoundingBox(temp)
                    if any(v != 0 for v in temp):
                        print(f"  Inertia Success: {temp}")
                        found_any = True
                        final_bbox[0] = min(final_bbox[0], temp[0], temp[3])
                        final_bbox[1] = min(final_bbox[1], temp[1], temp[4])
                        final_bbox[2] = min(final_bbox[2], temp[2], temp[5])
                        final_bbox[3] = max(final_bbox[3], temp[0], temp[3])
                        final_bbox[4] = max(final_bbox[4], temp[1], temp[4])
                        final_bbox[5] = max(final_bbox[5], temp[2], temp[5])
                except Exception as e:
                    print(f"  Inertia Error: {e}")

            except Exception as e:
                print(f"  General Error on Ref: {e}")

        if found_any:
            print(f"UNION SUCCESS: {final_bbox}")
        else:
            print("UNION FAILED: No measurable geometry found anywhere.")

    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_multi_union()
