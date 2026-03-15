import win32com.client
import pythoncom
import sys

def test_catia():
    print("Testing CATIA connection...")
    try:
        pythoncom.CoInitialize()
        print("CoInitialize successful.")
        
        try:
            catia = win32com.client.GetActiveObject("CATIA.Application")
            print(f"Connection successful! CATIA Name: {catia.Name}")
            print(f"Active Document: {catia.ActiveDocument.Name}")
        except Exception as e:
            print(f"GetActiveObject failed: {e}")
            
    except Exception as e:
        print(f"CoInitialize failed: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_catia()
