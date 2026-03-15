
import sys
import os
import win32com.client

# Add app directory to path to import services
sys.path.append(os.path.join(os.getcwd(), 'app'))
from app.services.geometry_service import geometry_service

def test_component(target_name):
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
    except:
        print("CATIA not found.")
        return

    doc = caa.ActiveDocument
    print(f"Active Document: {doc.Name}")
    
    # Dump tree structure for debugging
    print("\n--- Tree Overview (Top 2 Levels) ---")
    try:
        root = doc.Product
        print(f"Root: {root.Name}")
        for i in range(1, root.Products.Count + 1):
            p1 = root.Products.Item(i)
            print(f"  [{i}] {p1.Name}")
            try:
                for j in range(1, p1.Products.Count + 1):
                    p2 = p1.Products.Item(j)
                    print(f"    - {p2.Name}")
            except: pass
    except: pass

    sel = doc.Selection
    sel.Clear()
    
    target = None
    
    # Strategy 1: Search by Name
    print(f"\n[DEBUG] Searching for '{target_name}'...")
    try:
        # Note: Name is typically Instance Name in Search
        sel.Search(f"Name='*{target_name}*',all")
        print(f"[DEBUG] Search Match Count: {sel.Count}")
        if sel.Count > 0:
            for i in range(1, min(sel.Count, 5) + 1):
                print(f"  Match[{i}]: {sel.Item(i).Value.Name}")
            target = sel.Item(1).Value
    except Exception as e:
        print(f"[DEBUG] CATIA Search failed: {e}")

    # Strategy 2: Fallback to current Selection if nothing found by search
    if not target:
        sel.Clear()
        # Wait for user? No, just check if they ALREADY have something selected.
        # But my script clears it. Let's changed that.
        print("\n[DEBUG] Checking if user has anything selected manually...")
        # Since I cleared it at top of doc, I can't check what was there BEFORE the script.
        # I'll remove the sel.Clear() from the top.
        pass

    if not target:
        print(f"Target '{target_name}' not found.")
        return

    print(f"Found Target: {target.Name}")
    
    print(f"Measuring {target.Name}...")
    
    # Aggressively force Design Mode on root
    print("[DEBUG] Forcing Design Mode on assembly root...")
    try:
        doc.Product.ApplyDesignMode()
        # Recursively if needed
        for i in range(1, doc.Product.Products.Count + 1):
            try: doc.Product.Products.Item(i).ApplyDesignMode()
            except: pass
    except: pass

    result = geometry_service.get_bounding_box(target)
    
    print("\n--- Measurement Result ---")
    print(f"Size: {result.get('stock_size', 'N/A')}")
    print(f"Extents: x={result.get('x')}, y={result.get('y')}, z={result.get('z')}")
    print(f"Min: {result.get('xmin')}, {result.get('ymin')}, {result.get('zmin')}")
    print(f"Max: {result.get('xmax')}, {result.get('ymax')}, {result.get('zmax')}")

if __name__ == "__main__":
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        print(f"Active Document: {caa.ActiveDocument.Name}")
        
        def walk(prod, depth=0):
            print(f"{'  '*depth}- {prod.Name} (PN: {getattr(prod, 'PartNumber', 'N/A')})")
            try:
                for i in range(1, prod.Products.Count + 1):
                    walk(prod.Products.Item(i), depth + 1)
            except: pass
        
        print("\n--- Full Tree Walk ---")
        walk(caa.ActiveDocument.Product)
        
    except Exception as e:
        print(f"Failed to connect to CATIA: {e}")
        sys.exit(1)
