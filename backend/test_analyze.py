import win32com.client
import pythoncom

def test_analyze():
    caa = win32com.client.Dispatch("CATIA.Application")
    doc = caa.ActiveDocument
    
    # Let's find a CATPart in the session
    part_doc = None
    for i in range(1, caa.Documents.Count + 1):
        if ".CATPart" in caa.Documents.Item(i).Name:
            part_doc = caa.Documents.Item(i)
            break
            
    if not part_doc:
        print("No CATPart found")
        return
        
    print(f"Testing Analyze on {part_doc.Name}")
    part = part_doc.Part
    product = part_doc.Product
    
    try:
        vol = product.Analyze.Volume * 1000000000
        mass = product.Analyze.Mass
        print(f"Product.Analyze -> Vol: {vol:.2f} mm3, Mass: {mass:.3f} kg")
    except Exception as e:
        print(f"Product.Analyze Failed: {e}")

if __name__ == "__main__":
    test_analyze()
