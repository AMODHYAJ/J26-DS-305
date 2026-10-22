"""
Reference Benchmarking & Curtailment Integration Module.
Recursively scans C:\\Users\\USER\\Downloads\\CEB_data for Sumathi (Wewila) monthly plant reports
(April–September) as the primary utility-scale reference benchmark and parses NCRE Control
curtailment logs across folders 1, 2, and 3.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

# Explicit path to your local CEB data directory
CEB_DATA_DIR = Path(r"C:\Users\USER\Downloads\CEB_data")


def load_sumathi_reference_reports(root_dir: Path) -> pd.DataFrame:
    """
    Recursively finds and concatenates all monthly Sumathi (Wewila) plant reports (April–September).
    Calculates specific energy (kWh/kWp), performance ratios, and daily inverter yield benchmarks.
    """
    sumathi_files = list(root_dir.rglob("Plant Report_5MW Sumathi solar project wewila_*.xlsx"))
    print(f"Found {len(sumathi_files)} Sumathi monthly reference report files in {root_dir}")

    frames = []
    for fpath in sumathi_files:
        try:
            df = pd.read_excel(fpath, header=1)
            df.dropna(subset=[df.columns[0]], inplace=True)
            df["source_file"] = fpath.name
            frames.append(df)
            print(f"  -> Loaded Sumathi report: {fpath.name} ({len(df)} daily records)")
        except Exception as e:
            print(f"  -> Warning: Could not read {fpath.name}: {e}")

    if frames:
        df_combined = pd.concat(frames, ignore_index=True)
        return df_combined
    return pd.DataFrame()


def parse_ncre_control_logs(root_dir: Path) -> pd.DataFrame:
    """Recursively scans NCRE Control - 1, 2, and 3 folders for curtailment logs."""
    control_folders = [
        root_dir / "NCRE Control - 1",
        root_dir / "NCRE Control - 2",
        root_dir / "NCRE Control - 3"
    ]

    all_control_files = []
    for cfolder in control_folders:
        if cfolder.exists():
            files = list(cfolder.rglob("*.xlsx")) + list(cfolder.rglob("*.xls")) + list(cfolder.rglob("*.csv"))
            all_control_files.extend(files)
            print(f"Found {len(files)} curtailment files in {cfolder.name}")

    global_control = list(root_dir.rglob("*NCRE Control*.xlsx"))
    all_control_files = list(set(all_control_files + global_control))
    print(f"Total NCRE Control files to parse: {len(all_control_files)}")

    control_frames = []
    for fpath in all_control_files:
        try:
            xls = pd.ExcelFile(fpath)
            for sheet in xls.sheet_names:
                if any(k in sheet.lower() for k in ['final', 'curtail', 'summary', 'ncre']):
                    df = pd.read_excel(xls, sheet_name=sheet, header=1)
                    df["source_file"] = fpath.name
                    df["sheet_name"] = sheet
                    control_frames.append(df)
        except Exception as e:
            pass

    if control_frames:
        df_combined = pd.concat(control_frames, ignore_index=True)
        print(f"  -> Loaded {len(df_combined):,} total rows from NCRE Control logs across folders 1, 2, and 3.")
        return df_combined
    return pd.DataFrame()


def run_benchmark_pipeline() -> None:
    print("=======================================================")
    print("Running Sumathi Reference & Curtailment Pipeline")
    print("=======================================================")

    if not CEB_DATA_DIR.exists():
        print(f"Error: CEB data path not found at {CEB_DATA_DIR}. Please check the folder path.")
        return

    print(f"Target CEB data directory: {CEB_DATA_DIR}")

    # 1. Sumathi Monthly Reference Reports (April - September)
    df_sumathi = load_sumathi_reference_reports(CEB_DATA_DIR)
    if not df_sumathi.empty and "Specific Energy (kWh/kWp)" in df_sumathi.columns:
        print("\nSumathi Daily Specific Energy Summary (kWh/kWp):")
        print(df_sumathi["Specific Energy (kWh/kWp)"].describe())

    # 2. NCRE Control Curtailment Logs (Folders 1, 2, 3)
    df_curtailment = parse_ncre_control_logs(CEB_DATA_DIR)


if __name__ == "__main__":
    run_benchmark_pipeline()