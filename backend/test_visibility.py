"""
Debug script v2: Check GetShow() return values more thoroughly.
"""
import win32com.client

def check_children(product, doc, depth=0, max_depth=3):
    sel = doc.Selection
    try:
        com_prod = product.com_object if hasattr(product, "com_object") else product
        count = com_prod.Products.Count
    except:
        return
    
    for i in range(1, count + 1):
        child = com_prod.Products.Item(i)
        name = child.Name
        indent = "  " * depth

        try:
            sel.Clear()
            sel.Add(child)
            show_result = sel.VisProperties.GetShow()
            # Unpack if tuple
            if isinstance(show_result, tuple):
                show_val = show_result[1] if len(show_result) > 1 else show_result[0]
            else:
                show_val = show_result
            
            # catCatVisPropertyNoShowAttr = 1 means hidden
            status = "HIDDEN" if show_val == 1 else "VISIBLE"
            print(f"{indent}[{i}] {name:50s}  raw={show_result}  val={show_val}  => {status}")
        except Exception as e:
            print(f"{indent}[{i}] {name:50s}  ERROR: {e}")
        
        if depth < max_depth:
            check_children(child, doc, depth + 1, max_depth)

def main():
    caa = win32com.client.GetActiveObject("CATIA.Application")
    doc = caa.ActiveDocument
    product = doc.Product
    
    print(f"Document: {doc.Name}")
    print(f"Top product: {product.Name}")
    print("=" * 80)
    
    check_children(product, doc)
    
    doc.Selection.Clear()
    print("\nDone.")

if __name__ == "__main__":
    main()
