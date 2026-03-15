import win32com.client
import time

def test_product_instance_meas():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        active_doc = caa.ActiveDocument
        prod = active_doc.Product
        
        if prod.Products.Count == 0:
            print("No products.")
            return
            
        child = prod.Products.Item(1)
        print(f"Testing on Product Instance: {child.Name}")
        
        spa = active_doc.GetWorkbench("SPAWorkbench")
        
        try:
            m = spa.GetMeasurable(child)
            b = [0.0]*6
            m.GetBoundaryBox(b)
            print(f"    Success! Box: {b}")
            dx = abs(b[3]-b[0])*1000
            dy = abs(b[4]-b[1])*1000
            dz = abs(b[5]-b[2])*1000
            print(f"    Dimensions (mm): {dx:.2f} x {dy:.2f} x {dz:.2f}")
        except Exception as e:
            print(f"    Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_product_instance_meas()
