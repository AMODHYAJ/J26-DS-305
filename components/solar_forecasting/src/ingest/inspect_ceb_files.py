"""Intake report for CEB / plant-owner files (Excel or CSV).

Keep the real files OUTSIDE the git repo and point to them with C1_DATA_DIR:
    PowerShell:  $env:C1_DATA_DIR = "C:\\Users\\USER\\c1_data"
    Run:         python src/ingest/inspect_ceb_files.py            (structure only)
                 python src/ingest/inspect_ceb_files.py --show-rows (also prints 3 rows)

By default only the STRUCTURE is printed (sheets, columns, types, missing share,
time range and step, id counts, value ranges), so the output is safe to share.
Nothing is written to disk.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

EXTS = {".xlsx", ".xls", ".csv"}
TIME_HINTS = ("time", "date", "stamp", "datetime")
ID_HINTS = ("plant", "feeder", "station", "substation", "transformer", "sin", "id", "name")


def find_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in EXTS and not p.name.startswith("~$"))


def guess_time_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    for col in df.columns:
        if any(h in str(col).lower() for h in TIME_HINTS):
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().mean() > 0.8:
                return col
    return None


def describe_time(df: pd.DataFrame, col: str) -> None:
    t = pd.to_datetime(df[col], errors="coerce").dropna().sort_values()
    if len(t) < 2:
        print(f"  time column '{col}': fewer than 2 valid timestamps")
        return
    steps = t.diff().dropna()
    step = steps.median()
    share = float((steps == step).mean())
    gaps = int((steps > 3 * step).sum()) if step > pd.Timedelta(0) else 0
    print(f"  time column '{col}': {t.iloc[0]} -> {t.iloc[-1]}  ({len(t)} stamps)")
    print(f"  typical step: {step}  (share of steps equal to it: {share:.2f}, gaps > 3 steps: {gaps}, "
          f"duplicates: {int(t.duplicated().sum())})")
    print(f"  timezone info present: {t.dt.tz is not None}")


def describe_frame(df: pd.DataFrame, show_rows: bool) -> None:
    print(f"  shape: {df.shape}")
    df = df.dropna(how="all").dropna(axis=1, how="all")
    for col in df.columns:
        s = df[col]
        line = f"  - {str(col)[:45]:45s} {str(s.dtype):14s} missing {s.isna().mean():6.1%}"
        if pd.api.types.is_numeric_dtype(s) and s.notna().any():
            line += f"  min {s.min():.4g}  max {s.max():.4g}  negative {int((s < 0).sum())} ({float((s < 0).mean()):.2%})  zero {float((s == 0).mean()):.1%}"
        elif any(h in str(col).lower() for h in ID_HINTS):
            line += f"  distinct {s.nunique()}"
        print(line)
    tcol = guess_time_column(df)
    if tcol is not None:
        describe_time(df, tcol)
    else:
        print("  no time column found (static table or unusual header row)")
    if show_rows:
        print(df.head(3).to_string())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=os.environ.get("C1_DATA_DIR"))
    ap.add_argument("--show-rows", action="store_true", help="also print the first 3 rows (may contain sensitive values)")
    args = ap.parse_args()
    if not args.folder:
        print("Set C1_DATA_DIR or pass a folder path. Keep CEB files outside the git repository.")
        return 1
    folder = Path(args.folder)
    files = find_files(folder)
    print(f"{len(files)} data file(s) under {folder}")
    for path in files:
        print("\n" + "=" * 70 + f"\n{path.relative_to(folder)}\n" + "=" * 70)
        try:
            if path.suffix.lower() == ".csv":
                describe_frame(pd.read_csv(path, low_memory=False), args.show_rows)
            else:
                xls = pd.ExcelFile(path)
                print(f"sheets: {xls.sheet_names}")
                for sheet in xls.sheet_names:
                    print(f"\n--- sheet '{sheet}' ---")
                    describe_frame(pd.read_excel(xls, sheet_name=sheet), args.show_rows)
        except Exception as exc:  # report and continue with the next file
            print(f"  could not read: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())