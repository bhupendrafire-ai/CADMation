import win32com.client
import logging
import time

logging.basicConfig(level=logging.INFO)

def main():
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        print(f"Active Document: {doc.Name}")
        
        if "CATPart" not in doc.Name:
            print("Not a Part document.")
            return

        part = doc.Part
        print(f"Workbench: {catia.ActiveWindow.ActiveViewer.ActiveViewpoint.ProjectionMode}") # Rough check
        
        print("\n--- BODIES ---")
        for b in part.Bodies:
            print(f" - Body: {b.Name}")
            try:
                # Try to count shapes
                print(f"   Shapes: {b.Shapes.Count}")
            except: pass

        print("\n--- GEOMETRICAL SETS ---")
        for gs in part.HybridBodies:
            print(f" - Set: {gs.Name}")

        print("\n--- ACTIVE SELECTION ---")
        sel = doc.Selection
        sel.Clear()
        sel.Add(part)
        print(f"Selected: {sel.Item(1).Value.Name if sel.Count > 0 else 'None'}")

        # Try to find Rough Stock command alternatives
        print("\nTesting 'Rough Stock' variations...")
        variations = ["Rough Stock", "Rough_Stock", "RoughStock", "WS_RoughStock"]
        for v in variations:
            try:
                # We can't easily check 'status' without running, 
                # but we can see if it triggers an error immediately
                # Actually, catia.StartCommand is enough.
                pass
            except: pass

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
