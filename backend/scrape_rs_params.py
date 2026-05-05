import win32com.client
import sys
import os

def final_scrape():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # We'll just search for ANY parameters named DX, DY, DZ in the entire doc
        # This often works because Rough Stock creates internal parameters.
        print("Searching for DX, DY, DZ parameters...")
        params = ["DX", "DY", "DZ", "RoughStockX", "RoughStockY", "RoughStockZ"]
        results = {}
        for p_name in params:
            sel.Clear()
            sel.Search(f"Name=*{p_name}*,all")
            if sel.Count > 0:
                for i in range(1, sel.Count + 1):
                    p = sel.Item(i).Value
                    try:
                        results[p.Name] = p.ValueAsString()
                        print(f"FOUND: {p.Name} = {p.ValueAsString()}")
                    except: pass
        
        # If nothing found, we'll try the RoughStockService calculation ONE LAST TIME
        # but with a manual coordinate basis if we can get it.
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    final_scrape()
