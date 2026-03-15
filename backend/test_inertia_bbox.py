import win32com.client
import time

def test_inertia_bbox():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        prod = active_doc.Product
        
        if prod.Products.Count == 0: return
        child = prod.Products.Item(1)
        print(f"Testing Inertia BBox on: {child.Name}")
        
        try:
            # Analyze objects are available on Product instances
            analyze = child.Analyze
            inertia = analyze.Inertia
            
            # Inertia has a GetBoundingBox method? 
            # Actually, most pycatia users use:
            bbox = [0.0] * 6
            inertia.GetBoundingBox(bbox)
            print(f"  Inertia Success! Box: {bbox}")
            dx = abs(bbox[3]-bbox[0])*1000
            dy = abs(bbox[4]-bbox[1])*1000
            print(f"  Dims (mm): {dx:.2f} x {dy:.2f}")
        except Exception as e:
            print(f"  Inertia Failed: {e}")
            
            # Try Analyze.GetBoundingBox directly?
            try:
                bbox = [0.0]*6
                analyze.GetBoundingBox(bbox)
                print(f"  Analyze.GetBoundingBox Success! Box: {bbox}")
            except Exception as e2:
                print(f"  Analyze.GetBoundingBox Failed: {e2}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_inertia_bbox()
