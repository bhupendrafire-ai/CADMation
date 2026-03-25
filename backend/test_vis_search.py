import sys, os, time
import win32com.client
import pythoncom

def test_visibility_search():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        print(f"Active Document: {doc.Name}")
        
        # Select the part instance the user cares about (e.g. 002_UPPER SHOE)
        sel = doc.Selection
        sel.Clear()
        
        # We search specifically for VISIBLE bodies in the ACTIVE WINDOW.
        # This is the most "human-like" search.
        # String: "CATPrtSearch.Body.Visibility=Visible,all"
        # Or even better: "CATPrtSearch.Body,all" and then filter by VisProperties
        
        print("Executing Selection.Search for VISIBLE bodies...")
        try:
            # We use 'all' to search the entire tree of the active doc
            sel.Search("CATPrtSearch.Body.Visibility=Visible,all")
        except Exception as se:
            print(f"Search failed: {se}")
            return

        print(f"Visible bodies found: {sel.Count}")
        for i in range(1, sel.Count + 1):
            item = sel.Item(i).Value
            print(f"[{i}] {item.Name} (Path: {getattr(item, 'FullName', 'N/A')})")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # sel.Clear()
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_visibility_search()
