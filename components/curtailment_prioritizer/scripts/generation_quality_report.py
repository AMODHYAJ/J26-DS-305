
from pathlib import Path
import pandas as pd


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "artifacts"

GENERATION_FILE = (
        DATA_DIR / "raw" / "ceb_embilipitiya_plants_15min.csv"
)

SUMMARY_FILE = ARTIFACTS_DIR / "generation_quality_summary.csv"
DAILY_FILE = ARTIFACTS_DIR / "generation_daily_coverage.csv"
GAPS_FILE = ARTIFACTS_DIR / "generation_gaps_over_15min.csv"
INVALID_FILE = ARTIFACTS_DIR / "generation_invalid_records.csv"

EXPECTED_INTERVAL_MINUTES = 15

TARGET_PLANTS = {
    "6470900542": "Laugfs Solar",
    "6470900534": "Irish & Eco Solar",
    "6470900607": "Dimo Solar / Thunkama",
    "6470900828": "Chandrikawewa Floating Solar",
    "6470900836": "Kiriibbanwewa Floating Solar",
}


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def normalise_account(value):
    """Normalise account identifiers without losing leading digits."""
    if pd.isna(value):
        return ""

    text = str(value).strip()

    # Handle identifiers accidentally read as numbers like 6470900542.0
    if text.endswith(".0"):
        text = text[:-2]

    return text


def find_column(df, possible_names):
    """Find a column using case-insensitive aliases."""
    lookup = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for name in possible_names:
        if name.lower() in lookup:
            return lookup[name.lower()]

    return None


def save_csv(df, path):
    """Save a report using Excel-friendly UTF-8 encoding."""
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ============================================================
# 3. LOAD DATA
# ============================================================

def main():
    print("=" * 70)
    print("GENERATION DATA QUALITY REPORT")
    print("=" * 70)

    if not GENERATION_FILE.exists():
        raise FileNotFoundError(
            f"\nGeneration file not found:\n{GENERATION_FILE}\n\n"
            "Place the CSV at:\n"
            "components/curtailment_prioritizer/data/raw/"
            "ceb_embilipitiya_plants_15min.csv\n"
            "Alternatively, update GENERATION_FILE in this script."
        )

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nReading: {GENERATION_FILE.name}")

    # Keep account numbers as text.
    df = pd.read_csv(
        GENERATION_FILE,
        dtype={"Account Number": "string"},
        low_memory=False,
    )

    print(f"Total source rows: {len(df):,}")
    print(f"Source columns: {df.columns.tolist()}")

    # ========================================================
    # 4. IDENTIFY THE REQUIRED COLUMNS
    # ========================================================

    account_col = find_column(
        df,
        [
            "ac_number",
            "account_number",
            "account_no",
            "account number",
        ],
    )

    # Prefer datetime_utc because it explicitly identifies UTC.
    timestamp_col = find_column(
        df,
        [
            "datetime_utc",
            "timestamp",
            "datetime",
            "date_time",
            "timestamp_str",
            "time",
        ],
    )

    generation_col = find_column(
        df,
        [
            "generation_kw",
            "generation_kwh",
            "generation_mwh",
            "generation",
            "energy",
            "value",
        ],
    )

    required_columns = {
        "account number": account_col,
        "timestamp": timestamp_col,
        "generation": generation_col,
    }

    missing = [
        name
        for name, column in required_columns.items()
        if column is None
    ]

    if missing:
        raise ValueError(
            f"\nCould not identify these required fields: {missing}\n"
            f"Actual columns: {df.columns.tolist()}\n"
            "Update the column aliases in the script."
        )

    print("\nColumn mapping:")
    print(f"Account number: {account_col}")
    print(f"Timestamp:      {timestamp_col}")
    print(f"Generation:     {generation_col}")

    # ========================================================
    # 5. STANDARDISE THE DATA
    # ========================================================

    data = pd.DataFrame({
        "ac_number": df[account_col].map(normalise_account),
        "timestamp_original": df[timestamp_col].astype("string"),
        "generation_original": df[generation_col],
    })

    # Preserve UTC-aware timestamps.
    data["timestamp"] = pd.to_datetime(
        data["timestamp_original"],
        errors="coerce",
        utc=True,
    )

    data["generation"] = pd.to_numeric(
        data["generation_original"],
        errors="coerce",
    )

    # Keep only the five target plants.
    data = data[
        data["ac_number"].isin(TARGET_PLANTS.keys())
    ].copy()

    if data.empty:
        raise ValueError(
            "\nNo records matched the five target account numbers.\n"
            "Check the account-number values in the source CSV."
        )

    print(f"\nRows belonging to target plants: {len(data):,}")

    # ========================================================
    # 6. INVALID RECORDS
    # ========================================================

    invalid_timestamp = data["timestamp"].isna()
    invalid_generation = data["generation"].isna()

    invalid_mask = invalid_timestamp | invalid_generation
    invalid = data.loc[invalid_mask].copy()

    invalid["invalid_timestamp"] = invalid_timestamp.loc[
        invalid.index
    ]

    invalid["invalid_generation"] = invalid_generation.loc[
        invalid.index
    ]

    # Negative values are flagged for review, not automatically
    # discarded because their meaning depends on the source.
    invalid["negative_generation_flag"] = (
            invalid["generation"] < 0
    )

    save_csv(invalid, INVALID_FILE)

    valid = data.loc[~invalid_mask].copy()

    # ========================================================
    # 7. DUPLICATE TIMESTAMPS
    # ========================================================

    duplicate_mask = valid.duplicated(
        subset=["ac_number", "timestamp"],
        keep=False,
    )

    duplicates = valid.loc[duplicate_mask].copy()

    # Exclude duplicate timestamp rows from coverage calculations
    # by keeping the first occurrence. Duplicates are still reported.
    unique = valid.drop_duplicates(
        subset=["ac_number", "timestamp"],
        keep="first",
    ).copy()

    print(f"Invalid rows: {len(invalid):,}")
    print(f"Rows involved in duplicate timestamps: {len(duplicates):,}")
    print(f"Unique valid readings: {len(unique):,}")

    # ========================================================
    # 8. DAILY COVERAGE
    # ========================================================

    daily_rows = []

    for ac_number, plant_name in TARGET_PLANTS.items():
        plant = unique[
            unique["ac_number"] == ac_number
            ].sort_values("timestamp")

        if plant.empty:
            continue

        daily_counts = (
            plant.assign(
                date=plant["timestamp"].dt.strftime("%Y-%m-%d")
            )
            .groupby("date")
            .size()
        )

        first_day = plant["timestamp"].min().floor("D")
        last_day = plant["timestamp"].max().floor("D")

        for day in pd.date_range(first_day, last_day, freq="D"):
            date_string = day.strftime("%Y-%m-%d")
            observed = int(daily_counts.get(date_string, 0))

            daily_rows.append({
                "ac_number": ac_number,
                "plant_name": plant_name,
                "date": date_string,
                "observed_readings": observed,
                "expected_readings_full_day": 96,
                "missing_readings_full_day": max(0, 96 - observed),
                "coverage_pct_full_day": round(
                    observed / 96 * 100, 2
                ),
                "interpretation": (
                    "No readings"
                    if observed == 0
                    else (
                        "Check partial-day boundaries"
                        if observed < 96
                        else "96 readings; inspect timestamps for gaps"
                    )
                ),
            })

    daily_df = pd.DataFrame(
        daily_rows,
        columns=[
            "ac_number",
            "plant_name",
            "date",
            "observed_readings",
            "expected_readings_full_day",
            "missing_readings_full_day",
            "coverage_pct_full_day",
            "interpretation",
        ],
    )

    save_csv(daily_df, DAILY_FILE)

    # ========================================================
    # 9. GAPS BETWEEN CONSECUTIVE READINGS
    # ========================================================

    gap_rows = []

    for ac_number, plant_name in TARGET_PLANTS.items():
        plant = unique[
            unique["ac_number"] == ac_number
            ].sort_values("timestamp")

        times = plant["timestamp"].reset_index(drop=True)

        if len(times) < 2:
            continue

        for i in range(1, len(times)):
            previous = times.iloc[i - 1]
            current = times.iloc[i]

            gap_minutes = (
                                  current - previous
                          ).total_seconds() / 60

            if gap_minutes > EXPECTED_INTERVAL_MINUTES:
                # Estimate missing 15-minute slots between readings.
                missing_slots = max(
                    0,
                    int(round(
                        gap_minutes / EXPECTED_INTERVAL_MINUTES
                    )) - 1,
                    )

                gap_rows.append({
                    "ac_number": ac_number,
                    "plant_name": plant_name,
                    "previous_timestamp_utc": previous.isoformat(),
                    "next_timestamp_utc": current.isoformat(),
                    "gap_minutes": round(gap_minutes, 2),
                    "estimated_missing_15min_slots": missing_slots,
                })

    gaps_df = pd.DataFrame(
        gap_rows,
        columns=[
            "ac_number",
            "plant_name",
            "previous_timestamp_utc",
            "next_timestamp_utc",
            "gap_minutes",
            "estimated_missing_15min_slots",
        ],
    )

    save_csv(gaps_df, GAPS_FILE)

    # ========================================================
    # 10. SUMMARY BY PLANT
    # ========================================================

    summary_rows = []

    for ac_number, plant_name in TARGET_PLANTS.items():
        raw_plant = data[
            data["ac_number"] == ac_number
            ]

        plant = unique[
            unique["ac_number"] == ac_number
            ]

        plant_invalid = invalid[
            invalid["ac_number"] == ac_number
            ]

        plant_duplicates = duplicates[
            duplicates["ac_number"] == ac_number
            ]

        plant_gaps = gaps_df[
            gaps_df["ac_number"] == ac_number
            ]

        if plant.empty:
            summary_rows.append({
                "ac_number": ac_number,
                "plant_name": plant_name,
                "status": "NO VALID DATA",
                "raw_rows": len(raw_plant),
                "unique_valid_readings": 0,
                "duplicate_rows": len(plant_duplicates),
                "invalid_rows": len(plant_invalid),
                "first_timestamp_utc": "",
                "last_timestamp_utc": "",
                "largest_gap_hours": None,
                "gaps_over_15min": len(plant_gaps),
                "estimated_missing_slots": (
                    int(plant_gaps[
                            "estimated_missing_15min_slots"
                        ].sum())
                    if not plant_gaps.empty
                    else 0
                ),
            })
            continue

        largest_gap_hours = (
            plant_gaps["gap_minutes"].max() / 60
            if not plant_gaps.empty
            else 0
        )

        summary_rows.append({
            "ac_number": ac_number,
            "plant_name": plant_name,
            "status": "REVIEW REQUIRED",
            "raw_rows": len(raw_plant),
            "unique_valid_readings": len(plant),
            "duplicate_rows": len(plant_duplicates),
            "invalid_rows": len(plant_invalid),
            "first_timestamp_utc": (
                plant["timestamp"].min().isoformat()
            ),
            "last_timestamp_utc": (
                plant["timestamp"].max().isoformat()
            ),
            "largest_gap_hours": round(
                largest_gap_hours, 2
            ),
            "gaps_over_15min": len(plant_gaps),
            "estimated_missing_slots": (
                int(plant_gaps[
                        "estimated_missing_15min_slots"
                    ].sum())
                if not plant_gaps.empty
                else 0
            ),
        })

    summary_df = pd.DataFrame(summary_rows)
    save_csv(summary_df, SUMMARY_FILE)

    # ========================================================
    # 11. PRINT RESULTS
    # ========================================================

    print("\n" + "=" * 70)
    print("GENERATION DATA QUALITY SUMMARY")
    print("=" * 70)

    display_columns = [
        "plant_name",
        "raw_rows",
        "unique_valid_readings",
        "duplicate_rows",
        "invalid_rows",
        "largest_gap_hours",
        "gaps_over_15min",
    ]

    print(
        summary_df[display_columns].to_string(index=False)
    )

    print("\nReports created:")
    print(f"1. {SUMMARY_FILE}")
    print(f"2. {DAILY_FILE}")
    print(f"3. {GAPS_FILE}")
    print(f"4. {INVALID_FILE}")

    print("\nImportant notes:")
    print("- Original generation CSV has not been modified.")
    print("- Missing readings are not treated as zero generation.")
    print("- Missing readings do not prove that curtailment occurred.")
    print("- Generation values are preserved in their original unit.")
    print("- Confirm units before converting power into energy.")
    print("- Duplicate timestamps are reported, not silently ignored.")

    print("\nQuality report completed.")


if __name__ == "__main__":
    main()
