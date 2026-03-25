import win32gui

def enum_windows_callback(hwnd, titles):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title:
            titles.append(title)

def main():
    titles = []
    win32gui.EnumWindows(enum_windows_callback, titles)
    print("--- Visible Windows ---")
    for t in sorted(titles):
        print(t)

if __name__ == "__main__":
    main()
