
import win32com.client
import pythoncom

def list_docs_and_selections():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        print(f"Total Documents: {caa.Documents.Count}")
        print(f"Active Document: {caa.ActiveDocument.Name}")
        
        for i in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(i)
            try:
                sel_count = doc.Selection.Count
                print(f"Document {i}: {doc.Name} | Selection Count: {sel_count}")
                if sel_count > 0:
                    for j in range(1, sel_count + 1):
                        item = doc.Selection.Item(j).Value
                        print(f"  - Selected: {getattr(item, 'Name', 'Unknown')} ({type(item).__name__})")
            except:
                print(f"Document {i}: {doc.Name} | (Selection inaccessible)")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_docs_and_selections()
