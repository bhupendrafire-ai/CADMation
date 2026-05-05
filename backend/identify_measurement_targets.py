import win32com.client
import sys
import os

def identify_objects():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        print(f"Active Document: {doc.Name}")
        
        def find_obj(prod, target_name):
            if target_name.upper() in prod.Name.upper() or target_name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    res = find_obj(prod.Products.Item(i), target_name)
                    if res: return res
            except: pass
            return None

        # 1. Find INPUT PART_01
        input_part_01 = find_obj(doc.Product, "INPUT PART_01")
        if input_part_01:
            print(f"Found INPUT PART_01: {input_part_01.Name}")
            # Look for AP_AXIS under it
            try:
                ref = input_part_01.ReferenceProduct
                if ref and hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                    part = ref.Parent.Part
                    for i in range(1, part.AxisSystems.Count + 1):
                        ax = part.AxisSystems.Item(i)
                        print(f"  Axis found: {ax.Name}")
                        if "AP_AXIS" in ax.Name.upper():
                            print(f"  SUCCESS! Found AP_AXIS in INPUT PART_01")
            except: pass
        else:
            print("INPUT PART_01 not found directly, searching globally...")

        # 2. Find 202_LOWER PLATE
        lower_plate = find_obj(doc.Product, "202_LOWER PLATE")
        if lower_plate:
            print(f"Found 202_LOWER PLATE: {lower_plate.Name}")
        else:
            print("202_LOWER PLATE not found")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    identify_objects()
