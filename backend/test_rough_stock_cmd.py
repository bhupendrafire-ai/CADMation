import win32com.client
import time

def main():
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        part_doc = catia.ActiveDocument
        part = part_doc.Part
        selection = part_doc.Selection
        
        # Select the first body
        body = part.Bodies.Item(1)
        selection.Clear()
        selection.Add(body)
        
        print(f"Selected: {body.Name}")
        print("Tring to start 'Rough Stock' command...")
        
        # Try different names for the command
        commands = ["Rough Stock", "RoughStock", "Rough_Stock", "CATDrwRoughStockCmd"]
        for cmd in commands:
            try:
                print(f"Executing: {cmd}")
                catia.StartCommand(cmd)
                time.sleep(2) # Wait for dialog
                # Check for active window or something? Hard to do via COM.
                # Just see if it crashes.
            except Exception as e:
                print(f"Command '{cmd}' failed: {e}")

        print("Check CATIA for a dialog box.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
