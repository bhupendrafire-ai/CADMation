
import win32com.client
import sys

def check_status():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        print(f"ACTIVE_DOCUMENT|{doc.Name}")
        print(f"FULL_PATH|{doc.FullName}")
    except Exception as e:
        print(f"ERROR|{e}")

if __name__ == "__main__":
    check_status()
