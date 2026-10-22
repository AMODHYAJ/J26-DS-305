
from pathlib import Path
import zipfile
import csv
import pandas as pd


# ============================================================
# 1. PROJECT PATHS
# ============================================================

# Project component directory:
# components/curtailment_prioritizer/
ROOT = Path(__file__).resolve().parents[1]

# Source ZIP files:
RAW_DIR = ROOT / "data" / "raw"

CONTROL_ZIP = RAW_DIR / "NCRE_Control_History.zip"
GENERATION_ZIP = RAW_DIR / "NCRE_Solar_Generation.zip"

# Extraction folders:
CONTROL_DIR = RAW_DIR / "control"
GENERATION_DIR = RAW_DIR / "generation"

# Audit reports:
ARTIFACTS_DIR = ROOT / "artifacts"
CONTROL_REPORT = ARTIFACTS_DIR / "control_audit.csv"
GENERATION_REPORT = ARTIFACTS_DIR / "generation_audit.csv"
SUMMARY_REPORT = ARTIFACTS_DIR / "audit_summary.txt"


# ============================================================
# 2. EXTRACT ZIP FILES
# ============================================================

def extract_archive(zip_path: Path, destination: Path):
    """Safely extract a trusted ZIP archive without path traversal."""

    if not zip_path.exists():
        raise FileNotFoundError(
            f"ZIP file not found: {zip_path}\n"
            "Check that the ZIP file is in the data/raw folder."
        )

    destination.mkdir(parents=True, exist_ok=True)

    # Skip extraction if files already exist.
    if any(destination.rglob("*")):
        print(f"\nAlready extracted; skipping: {zip_path.name}")
        return

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()

            if not target.is_relative_to(destination.resolve()):
                raise ValueError(
                    f"Unsafe ZIP member path detected: {member.filename}"
                )

        bad_file = archive.testzip()
        if bad_file:
            raise ValueError(
                f"ZIP integrity check failed at: {bad_file}"
            )

        archive.extractall(destination)

    print(f"Extracted: {zip_path.name}")


def extract_archives():
    print("\n" + "=" * 65)
    print("EXTRACTING SOURCE FILES")
    print("=" * 65)

    extract_archive(CONTROL_ZIP, CONTROL_DIR)
    extract_archive(GENERATION_ZIP, GENERATION_DIR)


# ============================================================
# 3. FIND SOURCE FILES
# ============================================================

def find_control_files():
    """Find Excel workbooks, including files in subfolders."""

    files = []

    for path in CONTROL_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in {
            ".xlsx", ".xls"
        }:
            files.append(path)

    return sorted(files)


def find_generation_files():
    """Find CSV files, including files in subfolders."""

    return sorted(
        path
        for path in GENERATION_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".csv"
    )


# ============================================================
# 4. AUDIT CONTROL WORKBOOKS
# ============================================================

def audit_control_files():
    files = find_control_files()
    results = []

    print("\n" + "=" * 65)
    print(f"CONTROL WORKBOOK AUDIT: {len(files)} FILES")
    print("=" * 65)

    for file in files:
        print(f"\nFILE: {file.name}")

        try:
            # Select the correct Excel engine.
            engine = "xlrd" if file.suffix.lower() == ".xls" else "openpyxl"

            with pd.ExcelFile(file, engine=engine) as workbook:
                sheet_names = workbook.sheet_names

                print("SHEETS:", sheet_names)

                for sheet in sheet_names:
                    try:
                        # Read headers and only a few sample rows.
                        df = pd.read_excel(
                            file,
                            sheet_name=sheet,
                            engine=engine,
                            nrows=5,
                        )

                        columns = [
                            str(column).strip()
                            for column in df.columns
                        ]

                        print(f"  SHEET: {sheet}")
                        print(f"  COLUMNS: {columns}")

                        results.append({
                            "file_name": str(file.relative_to(CONTROL_DIR)),
                            "sheet_name": sheet,
                            "status": "OK",
                            "row_count_sample": len(df),
                            "columns": " | ".join(columns),
                            "error": "",
                        })

                    except Exception as exc:
                        print(f"  SHEET ERROR: {sheet}: {exc}")

                        results.append({
                            "file_name": str(file.relative_to(CONTROL_DIR)),
                            "sheet_name": sheet,
                            "status": "SHEET_ERROR",
                            "row_count_sample": "",
                            "columns": "",
                            "error": str(exc),
                        })

        except Exception as exc:
            print(f"WORKBOOK ERROR: {exc}")

            results.append({
                "file_name": str(file.relative_to(CONTROL_DIR)),
                "sheet_name": "",
                "status": "FILE_ERROR",
                "row_count_sample": "",
                "columns": "",
                "error": str(exc),
            })

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(CONTROL_REPORT, index=False)

    print(f"\nControl audit saved to: {CONTROL_REPORT}")
    return len(files), results


# ============================================================
# 5. AUDIT GENERATION CSV FILES
# ============================================================

def read_csv_sample(file: Path):
    """Read a small sample while trying common CSV encodings."""

    last_error = None

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(
                file,
                nrows=5,
                sep=None,
                engine="python",
                encoding=encoding,
            )
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            last_error = exc

    raise ValueError(f"Unable to read CSV sample: {last_error}")


def audit_generation_files():
    files = find_generation_files()
    results = []

    print("\n" + "=" * 65)
    print(f"GENERATION CSV AUDIT: {len(files)} FILES")
    print("=" * 65)

    for file in files:
        print(f"\nFILE: {file.name}")

        try:
            df = read_csv_sample(file)
            columns = [
                str(column).strip()
                for column in df.columns
            ]

            print("COLUMNS:", columns)
            print(df.head(2).to_string(index=False))

            results.append({
                "file_name": str(file.relative_to(GENERATION_DIR)),
                "status": "OK",
                "row_count_sample": len(df),
                "columns": " | ".join(columns),
                "error": "",
            })

        except Exception as exc:
            print(f"CSV ERROR: {exc}")

            results.append({
                "file_name": str(file.relative_to(GENERATION_DIR)),
                "status": "FILE_ERROR",
                "row_count_sample": "",
                "columns": "",
                "error": str(exc),
            })

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(GENERATION_REPORT, index=False)

    print(f"\nGeneration audit saved to: {GENERATION_REPORT}")
    return len(files), results


# ============================================================
# 6. SAVE A SUMMARY
# ============================================================

def save_summary(control_count, control_results,
                 generation_count, generation_results):

    control_errors = sum(
        result["status"] != "OK"
        for result in control_results
    )

    generation_errors = sum(
        result["status"] != "OK"
        for result in generation_results
    )

    summary = [
        "NCRE DATA AUDIT SUMMARY",
        "=" * 40,
        "",
        f"Control Excel files discovered: {control_count}",
        f"Control audit errors: {control_errors}",
        "",
        f"Generation CSV files discovered: {generation_count}",
        f"Generation audit errors: {generation_errors}",
        "",
        "Note:",
        "This is a structural audit, not a curtailment calculation.",
        "Only five sample rows per sheet/file were inspected.",
        "No source data was modified.",
        ]

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_REPORT.write_text(
        "\n".join(summary),
        encoding="utf-8",
    )

    print("\n" + "\n".join(summary))
    print(f"\nSummary saved to: {SUMMARY_REPORT}")


# ============================================================
# 7. MAIN
# ============================================================

def main():
    print("NCRE DATA AUDIT STARTED")
    print(f"Project directory: {ROOT}")

    extract_archives()

    control_count, control_results = audit_control_files()

    generation_count, generation_results = audit_generation_files()

    save_summary(
        control_count,
        control_results,
        generation_count,
        generation_results,
    )

    print("\nAUDIT COMPLETED")


if __name__ == "__main__":
    main()
