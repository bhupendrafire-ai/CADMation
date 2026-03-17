import os
import sys
import threading
import time
import webbrowser


def _open_browser(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    import uvicorn

    host = os.environ.get("CADMATION_HOST", "127.0.0.1")
    port = int(os.environ.get("CADMATION_PORT", "8000"))
    url = f"http://{host}:{port}"

    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

