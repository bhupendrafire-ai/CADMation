import win32com.client
import time

def test_visibility_search():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        print("Starting batch visibility search...")
        start = time.time()
        
        # Search for all visible products/parts
        # Syntax: 'CATProd.Visible' or 'Visibility=Visible'
        # We'll try the most robust one:
        sel.Clear()
        # sel.Search("Visibility=Visible,all") # This is often the standard
        # Or: "CATProduct.Visibility=Visible,all"
        
        # Let's try to just find everything and check attributes if Search is tricky,
        # but Search is the intended way to do this blindly.
        try:
            sel.Search("State=Visible,all")
            count = sel.Count
            print(f"Found {count} visible items.")
            
            # Show the first few
            for i in range(1, min(count, 5) + 1):
                print(f" Visible Item {i}: {sel.Item(i).Value.Name}")
        except Exception as e:
            print(f"Search failed: {e}")
            
        print(f"Batch search took {time.time() - start:.2f}s")
        
        # Test if we can find Hidden items
        sel.Clear()
        try:
            sel.Search("State=Hidden,all")
            print(f"Found {sel.Count} hidden items.")
        except: pass

    except Exception as e:
        print(f"Major failure: {e}")

if __name__ == "__main__":
    test_visibility_search()
