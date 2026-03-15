import win32com.client
import time

def test_product_bbox():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        # Test if it's a product
        try:
            target = doc.Product
            print(f"Testing on Product: {target.Name}")
        except:
            print("Active document is not a product.")
            return

        # Method 1: SPAWorkbench on Product
        print("\nAttempting SPAWorkbench on Product directly...")
        try:
            spa = doc.GetWorkbench("SPAWorkbench")
            # Usually GetMeasurable(target) fails on a Product COM object 
            # unless it's a specific type, but let's try.
            measurable = spa.GetMeasurable(target)
            bbox = [0.0] * 6
            measurable.GetBoundaryBox(bbox)
            print(f"SPA Success! Box: {bbox}")
        except Exception as e:
            print(f"SPA Failed: {e}")

        # Method 2: Inertia (Analyze.Inertia)
        print("\nAttempting Inertia measurement...")
        try:
            # Note: Inertia often gives the AABB as well
            inertia = target.Analyze.Inertia
            # Inertia has GetBoundingBox? No, it has mass, etc.
            # But Analyze.GetBoundingBox?
            bbox = [0.0] * 6
            target.Analyze.GetBoundaryBox(bbox)
            print(f"Analyze.GetBoundaryBox Success! Box: {bbox}")
        except Exception as e:
            print(f"Analyze.GetBoundaryBox Failed: {e}")

    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_product_bbox()
