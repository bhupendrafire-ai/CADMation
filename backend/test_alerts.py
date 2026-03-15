import win32com.client

def test_alerts():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        print(f"Current DisplayFileAlerts: {caa.DisplayFileAlerts}")
        caa.DisplayFileAlerts = False
        print(f"Set DisplayFileAlerts to False")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_alerts()
