import win32com.client
import sys

def debug_axis():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        def find_product(prod, name):
            if name.upper() in prod.Name.upper() or name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_product(prod.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        adapter = find_product(doc.Product, "ADAPTER_LOWER_AND_UPPER_DIE")
        if not adapter: return
        
        part = adapter.ReferenceProduct.Parent.Part
        ax = None
        for i in range(1, part.AxisSystems.Count + 1):
            if "AP_AXIS" in part.AxisSystems.Item(i).Name.upper():
                ax = part.AxisSystems.Item(i)
                break
        
        if not ax: return
        
        print(f"DEBUGGING AXIS: {ax.Name}")
        print(f"TYPE: {type(ax)}")
        
        # Try different ways to get origin
        try:
            o = [0.0, 0.0, 0.0]
            ax.GetOrigin(o)
            print(f"Origin (GetOrigin): {o}")
        except Exception as e: print(f"GetOrigin failed: {e}")
        
        try:
            vx = [0.0, 0.0, 0.0]
            vy = [0.0, 0.0, 0.0]
            ax.GetVectors(vx, vy)
            print(f"Vectors (GetVectors): X={vx}, Y={vy}")
        except Exception as e: print(f"GetVectors failed: {e}")

        try:
            print(f"XAxis name: {ax.XAxis.Name}")
            dx = [0.0, 0.0, 0.0]
            ax.XAxis.GetDirection(dx)
            print(f"X Direction: {dx}")
        except Exception as e: print(f"XAxis access failed: {e}")

    except Exception as e:
        print(f"Main Error: {e}")

if __name__ == "__main__":
    debug_axis()
