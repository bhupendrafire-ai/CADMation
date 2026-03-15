
import win32com.client
import pythoncom

def list_windows():
    pythoncom.CoInitialize()
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        print(f"Windows Count: {caa.Windows.Count}")
        for i in range(1, caa.Windows.Count + 1):
            win = caa.Windows.Item(i)
            print(f"Window {i}: {win.Caption}")
            
        print(f"Active Window: {caa.ActiveWindow.Caption}")
        print(f"CATIA Caption: {caa.Caption}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_windows()
