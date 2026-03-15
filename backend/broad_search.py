
import win32com.client
import sys

def search_broad():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
    except:
        print("CATIA not found.")
        return

    doc = caa.ActiveDocument
    print(f"Active Document: {doc.Name}")
    sel = doc.Selection
    
    queries = [
        "Name='*STEEL*',all",
        "Part Number='*STEEL*',all",
        "Name='*LOWER*',all",
        "Part Number='*LOWER*',all"
    ]
    
    for q in queries:
        print(f"\n--- Running Search: {q} ---")
        try:
            sel.Clear()
            sel.Search(q)
            print(f"Match Count: {sel.Count}")
            for i in range(1, min(sel.Count, 10) + 1):
                obj = sel.Item(i).Value
                print(f"  [{i}] Name: {obj.Name}")
                if hasattr(obj, "PartNumber"):
                    print(f"      PartNumber: {obj.PartNumber}")
        except Exception as e:
            print(f"Search failed: {e}")

if __name__ == "__main__":
    search_broad()
