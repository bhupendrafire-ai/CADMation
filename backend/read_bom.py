import pandas as pd
import os

file_path = r"H:\CADMation\BOM_Outputs\BOM_BOM_2026-03-15_17-54.xlsx"

if os.path.exists(file_path):
    df = pd.read_excel(file_path, header=None)
    data = df.iloc[7:]
    
    # Flatten all names found in col 1 and 2
    all_names = data[1].dropna().astype(str).tolist() + data[2].dropna().astype(str).tolist()
    
    def check_exists(pattern):
        matches = [n for n in all_names if pattern.lower() in n.lower()]
        if matches:
            # Find the row for quantity
            row = data[(data[1].astype(str).str.contains(pattern, na=False, case=False)) | 
                       (data[2].astype(str).str.contains(pattern, na=False, case=False))]
            qty = row.iloc[0, 6] if not row.empty else "???"
            print(f"MATCH FOUND for '{pattern}': {matches[0]} | Qty: {qty}")
        else:
            print(f"NO MATCH for '{pattern}'")

    print("--- COMPLETE BOM SEARCH ---")
    search_terms = [
        "MAN ASSEMBLY", "LOWER ASSEMBLY", "LWR STD PART", "900-MAIN", "614-TRANS", 
        "LIFTER", "DTPK", "GSV", "BALANCER", "STOPPER", "STACKING", "EJECTION"
    ]
    for term in search_terms:
        check_exists(term)
        
else:
    print(f"File not found: {file_path}")
