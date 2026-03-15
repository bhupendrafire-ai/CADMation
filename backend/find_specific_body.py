
import win32com.client
import pythoncom
import os

def find_body_and_doc():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        target_body_name = "LOWER STEEL_1"
        target_doc = None
        
        print(f"Searching for Body: {target_body_name}")
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            if hasattr(doc, "Part"):
                try:
                    p = doc.Part
                    for b in p.Bodies:
                        if target_body_name.lower() in b.Name.lower():
                            print(f"FOUND!")
                            print(f"  Doc Name: {doc.Name}")
                            print(f"  Full Path: {doc.FullName}")
                            print(f"  Body Name: {b.Name}")
                            target_doc = doc
                            break
                    if target_doc: break
                except: continue
        
        if not target_doc:
            print("Target body not found in any open Part document.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_body_and_doc()
