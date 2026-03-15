import sys
import os
from pycatia import catia

def list_workbenches():
    try:
        caa = catia()
        # CATIA.Application doesn't have a direct "available workbenches" list
        # but we can try common ones to see what sticks
        doc = caa.active_document
        
        common_workbenches = [
            "SPAWorkbench",
            "PartWorkbench",
            "Drafting",
            "PrtCfg", # Part Design
            "GSD", # Generative Shape Design
            "CATShapeDesignWorkbench",
            "Assembly",
            "Manufacturing",
            "PPR"
        ]
        
        print(f"Testing workbenches on {doc.name}:")
        for wb_name in common_workbenches:
            try:
                wb = doc.get_workbench(wb_name)
                print(f"  [OK] {wb_name}")
            except:
                print(f"  [FAIL] {wb_name}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_workbenches()
