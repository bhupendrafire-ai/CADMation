
import win32com.client
import pythoncom
import os

def list_document_paths():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        print(f"Total Documents: {caa.Documents.Count}")
        
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            # Only log interesting ones to avoid 141 line spam
            if "steel" in doc.Name.lower() or "catpart" in doc.Name.lower():
                try:
                    print(f"Doc: {doc.Name}")
                    print(f"  Path: {doc.FullName}")
                except:
                    print(f"  Path: [ERROR OR UNSET]")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_document_paths()
