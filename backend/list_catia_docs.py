import win32com.client
import logging

logging.basicConfig(level=logging.INFO)

def main():
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        print(f"Active Document: {catia.ActiveDocument.Name}")
        print("\nAll Open Documents:")
        for doc in catia.Documents:
            print(f" - {doc.Name} ({doc.FullName})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
