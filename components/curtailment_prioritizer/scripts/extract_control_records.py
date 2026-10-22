
from pathlib import Path
import re
import pandas as pd


# ============================================================
# 1. PATHS AND SETTINGS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CONTROL_DIR = RAW_DIR / "control"
ARTIFACTS_DIR = ROOT / "artifacts"

CANDIDATES_FILE = ARTIFACTS_DIR / "control_record_candidates.csv"
INVENTORY_FILE = ARTIFACTS_DIR / "control_sheet_inventory.csv"
ERRORS_FILE = ARTIFACTS_DIR / "control_extraction_errors.csv"

# Terms used to identify candidate rows.
# These are search terms, NOT proof of curtailment.
SEARCH_TERMS = [
    "solar",
    "curtail",
    "curtailed",
    "fully curtail",
    "managed by nscc",
    "nscc",
]

# Known target plant names. Add exact names if the source
# workbooks use different spellings or abbreviations.
TARGET_PLANT_NAMES = [
    "Laugfs Solar",
    "Irish & Eco Solar",
    "Dimo Solar",
    "Thunkama",
    "Chandrikawewa Floating Solar",
    "Kiriibbanwewa Floating Solar",
]


# ============================================================
# 2. HELPERS
# ============================================================

def clean_text(value):
    """Convert a cell value to clean text."""
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in {"nan", "nat", "none"}:
        return ""

    return text


def row_text(values):
    """Combine non-empty cells into one searchable string."""
    return " | ".join(
        clean_text(value)
        for value in values
        if clean_text(value)
    )


def is_candidate(text):
    """Check whether a row contains a relevant search term."""
    text_lower = text.lower()

    return any(
        term.lower() in text_lower
        for term in SEARCH_TERMS
    )


def identify_target(text):
    """Identify known target plants when their names appear."""
    text_lower = text.lower()

    matches = [
        name
        for name in TARGET_PLANT_NAMES
        if name.lower() in text_lower
    ]

    return "; ".join(matches)


def find_excel_files():
    """Find XLSX and XLS files recursively."""
    if not CONTROL_DIR.exists():
        raise FileNotFoundError(
            f"Control folder not found: {CONTROL_DIR}\n"
            "Extract the control ZIP into data/raw/control first."
        )

    return sorted(
        path
        for path in CONTROL_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".xlsx", ".xls"}
        and not path.name.startswith("~$")
    )


# ============================================================
# 3. EXTRACT CANDIDATE ROWS
# ============================================================

def extract_control_records():
    files = find_excel_files()

    print("=" * 65)
    print("NCRE CONTROL RECORD EXTRACTION")
    print("=" * 65)
    print(f"Excel files found: {len(files)}")

    candidates = []
    inventory = []
    errors = []

    for file_number, file in enumerate(files, start=1):
        engine = (
            "xlrd"
            if file.suffix.lower() == ".xls"
            else "openpyxl"
        )

        print(f"[{file_number}/{len(files)}] {file.name}")

        try:
            with pd.ExcelFile(file, engine=engine) as workbook:
                for sheet_name in workbook.sheet_names:
                    try:
                        # Read the full sheet without assuming
                        # that headers are on the first row.
                        df = pd.read_excel(
                            workbook,
                            sheet_name=sheet_name,
                            header=None,
                            dtype=object,
                        )

                        inventory.append({
                            "file_name": file.name,
                            "sheet_name": sheet_name,
                            "row_count": len(df),
                            "column_count": len(df.columns),
                            "status": "OK",
                            "error": "",
                        })

                        if df.empty:
                            continue

                        # Preserve the first 8 rows as context.
                        # Some workbooks place the date/status
                        # heading above the plant table.
                        context = []

                        for row_index in range(min(8, len(df))):
                            values = df.iloc[row_index].tolist()
                            text = row_text(values)

                            if text:
                                context.append(
                                    f"Row {row_index + 1}: {text}"
                                )

                        context_text = "\n".join(context)

                        for row_index, row in df.iterrows():
                            values = row.tolist()
                            text = row_text(values)

                            if not text or not is_candidate(text):
                                continue

                            # Keep the original cell positions.
                            non_empty_cells = []

                            for col_index, value in enumerate(values):
                                value_text = clean_text(value)

                                if value_text:
                                    # Excel columns are 1-based.
                                    column_letter = ""
                                    number = col_index + 1

                                    while number:
                                        number, remainder = divmod(
                                            number - 1, 26
                                        )
                                        column_letter = (
                                                chr(65 + remainder)
                                                + column_letter
                                        )

                                    non_empty_cells.append(
                                        f"{column_letter}={value_text}"
                                    )

                            candidates.append({
                                "file_name": file.name,
                                "sheet_name": sheet_name,
                                "excel_row": row_index + 1,
                                "target_plant_match": identify_target(text),
                                "row_text": text,
                                "cell_values": " || ".join(
                                    non_empty_cells
                                ),
                                "sheet_top_rows": context_text,
                            })

                    except Exception as exc:
                        message = str(exc)

                        errors.append({
                            "file_name": file.name,
                            "sheet_name": sheet_name,
                            "error": message,
                        })

                        inventory.append({
                            "file_name": file.name,
                            "sheet_name": sheet_name,
                            "row_count": "",
                            "column_count": "",
                            "status": "SHEET_ERROR",
                            "error": message,
                        })

        except Exception as exc:
            errors.append({
                "file_name": file.name,
                "sheet_name": "",
                "error": str(exc),
            })

    # ========================================================
    # 4. SAVE REPORTS
    # ========================================================

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(candidates).to_csv(
        CANDIDATES_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(inventory).to_csv(
        INVENTORY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        errors,
        columns=["file_name", "sheet_name", "error"],
    ).to_csv(
        ERRORS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 65)
    print("EXTRACTION SUMMARY")
    print("=" * 65)
    print(f"Excel files scanned: {len(files)}")
    print(f"Candidate rows found: {len(candidates)}")
    print(f"Sheet inventory entries: {len(inventory)}")
    print(f"Errors: {len(errors)}")
    print(f"\nCandidates: {CANDIDATES_FILE}")
    print(f"Inventory:  {INVENTORY_FILE}")
    print(f"Errors:     {ERRORS_FILE}")
    print("\nExtraction complete.")
    print("Candidate rows require review before being treated as events.")


if __name__ == "__main__":
    extract_control_records()
