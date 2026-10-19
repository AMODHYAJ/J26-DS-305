"""
CEB Plant and Grid Data Ingestion Script
Inspects and loads CEB Excel files in the project workspace.
"""

import os
import pandas as pd

def inspect_ceb_files():
    data_dir = '.'  # Project root directory
    excel_files = [f for f in os.listdir(data_dir) if f.endswith('.xlsx')]

    print(f"Found {len(excel_files)} Excel files in project root:")
    for f in excel_files:
        print(f"\n" + "="*50)
        print(f"File: {f}")
        print("="*50)
        try:
            filepath = os.path.join(data_dir, f)
            xls = pd.ExcelFile(filepath)
            print(f"Sheet names: {xls.sheet_names}")

            for sheet in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet)
                print(f"\n--- Sheet: '{sheet}' (Shape: {df.shape}) ---")
                print(df.head(3))
        except Exception as e:
            print(f"Error reading {f}: {e}")

if __name__ == '__main__':
    inspect_ceb_files()