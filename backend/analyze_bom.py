import pandas as pd

file_path = r"H:\CADMation\BOM\S24SKH1205-OP50-PRC_PART_OFF-FOR_ALL_VARIENTS-BOM-13.05.24 (1).xlsx"

def analyze_full():
    try:
        # MFG ITEM
        df_mfg = pd.read_excel(file_path, sheet_name='MFG ITEM', header=None)
        print("--- MFG ITEM (All) ---")
        print(df_mfg.head(15).to_string())
        
        # STD ITEM
        df_std = pd.read_excel(file_path, sheet_name='STD ITEM', header=None)
        print("\n--- STD ITEM (All) ---")
        print(df_std.head(15).to_string())
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_full()
