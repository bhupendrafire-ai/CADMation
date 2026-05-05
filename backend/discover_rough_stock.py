import win32com.client
import sys

def main():
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        part_doc = catia.ActiveDocument
        
        if not hasattr(part_doc, "Part"):
            print("Active document is not a Part.")
            return

        part = part_doc.Part
        hsf = part.HybridShapeFactory
        sf = part.ShapeFactory
        
        print(f"--- HybridShapeFactory Methods ---")
        # Since we can't easily list COM methods in Python without TypeLib
        # We can try to guess or use a list of known candidates
        candidates = ["RoughStock", "Rough_Stock", "BoundingBox", "Bounding_Box", "Box", "Stock"]
        for c in candidates:
            try:
                attr = getattr(hsf, f"AddNew{c}", None)
                if attr:
                    print(f"Found: AddNew{c}")
                attr = getattr(hsf, c, None)
                if attr:
                    print(f"Found: {c}")
            except:
                pass

        print(f"\n--- ShapeFactory Methods ---")
        for c in candidates:
            try:
                attr = getattr(sf, f"AddNew{c}", None)
                if attr:
                    print(f"Found: AddNew{c}")
                attr = getattr(sf, c, None)
                if attr:
                    print(f"Found: {c}")
            except:
                pass
                
        # Try to find if a "Rough Stock" feature exists BY TYPE
        print(f"\nSearching for Rough Stock features by type...")
        selection = part_doc.Selection
        selection.Clear()
        # Common internal types for Rough Stock/Bounding Box
        types = ["HybridShapeRoughStock", "RoughStock", "BoundingBox", "HybridShapeBoundingBox", "Box"]
        for t in types:
            try:
                selection.Search(f"Type={t}, all")
                if selection.Count > 0:
                    print(f"Found {selection.Count} matches for type: {t}")
                    for i in range(1, selection.Count + 1):
                         item = selection.Item(i).Value
                         print(f"  Match {i}: {item.Name}")
                selection.Clear()
            except:
                pass

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
