import win32com.client
import win32gui
import win32con
import time
import sys
import os

def list_windows():
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            print(f"Window: {win32gui.GetWindowText(hwnd)} (Class: {win32gui.GetClassName(hwnd)})")
    win32gui.EnumWindows(cb, None)

def check_catia():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        print(f"CATIA Version: {caa.SystemConfiguration.Release}")
        doc = caa.ActiveDocument
        print(f"Active Document: {doc.Name}")
        print(f"Active Workbench: {caa.GetWorkbenchId()}")
        
        # Try to activate CATIA
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(1)
        
        print("Triggering c:Rough Stock...")
        shell.SendKeys("{ESC}{ESC}c:Rough Stock{ENTER}", 0)
        time.sleep(2)
        
        # List windows to see if any new dialog appeared
        list_windows()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_catia()
