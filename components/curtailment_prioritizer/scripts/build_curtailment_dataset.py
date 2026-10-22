
from pathlib import Path
import re
import zipfile
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
RAW = DATA / "raw"
OUTPUT = DATA / "curtailment_events.csv"

GENERATION_FILE = RAW / "ceb_embilipitiya_plants_15min.csv"
CONTROL_DIR = RAW / "control"
CONTROL_ZIP = RAW / "NCRE_Control_History.zip"

PLANTS = {
    "6470900542": "Laugfs Solar",
    "6470900534": "Irish & Eco Solar",
    "6470900607": "Dimo Solar",
    "6470900828": "Chandrikawewa Floating Solar",
    "6470900836": "Kiriibbanwewa Floating Solar",
}

ALIASES = {
    "6470900542": ["laugfs solar", "laugfs power", "embilipitiya 2 sbspii"],
    "6470900534": ["irish & eco solar", "iris eco", "irish eco"],
    "6470900607": ["dimo solar", "thunkama"],
    "6470900828": ["chandrikawewa"],
    "6470900836": ["kiriibbanwewa"],
}

def text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def normalize_account(value):
    value = text(value)
    if re.fullmatch(r"\d+\.0", value):
        value = value[:-2]
    if re.fullmatch(r"\d+(?:\.0+)?[eE][+-]?\d+", value):
        try:
            value = str(int(float(value)))
        except ValueError:
            pass
    return value

def find_account(row_text):
    normalized = normalize_account(row_text)
    for account in PLANTS:
        if account in normalized:
            return account

    lower = normalized.lower()
    for account, aliases in ALIASES.items():
        if any(alias in lower for alias in aliases):
            return account
    return None

def find_date(values, file_name, sheet_name):
    # Prefer a date explicitly embedded in the workbook or sheet name.
    candidates = [sheet_name, file_name] + [text(v) for v in values]
    patterns = [
        r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b",
        r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b",
    ]
    for candidate in candidates:
        for pattern in patterns:
            match = re.search(pattern, candidate)
            if not match:
                continue
            try:
                if pattern.startswith(r"\b(20"):
                    y, m, d = map(int, match.groups())
                else:
                    m, d, y = map(int, match.groups())
                return pd.Timestamp(year=y, month=m, day=d).date().isoformat()
            except ValueError:
                continue
    return ""

def find_time_window(sheet_text):
    # Examples: "from 9:00 TO 11:25", "9:00 am to 11:25 am"
    match = re.search(
        r"(?:from\s*)?(\d{1,2}:\d{2})\s*(am|pm)?\s*"
        r"(?:to|[-–])\s*(\d{1,2}:\d{2})\s*(am|pm)?",
        sheet_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return "", ""

    start, start_ampm, end, end_ampm = match.groups()

    def convert_time(value, ampm):
        hour, minute = map(int, value.split(":"))
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
        return f"{hour:02d}:{minute:02d}"

    return convert_time(start, start_ampm), convert_time(end, end_ampm)

def find_power_before_schedule(values):
    # Look for a labelled value in the same sheet.
    for i, value in enumerate(values):
        if "power before schedule" in text(value).lower():
            for following in values[i + 1:i + 4]:
                match = re.search(r"\d+(?:\.\d+)?", text(following).replace(",", ""))
                if match:
                    return float(match.group())
    return None

def load_generation():
    df = pd.read_csv(GENERATION_FILE)
    df["account"] = df["Account Number"].map(normalize_account)
    df["timestamp"] = pd.to_datetime(
        df["datetime_utc"], errors="coerce", utc=True
    )
    df["generation_kw"] = pd.to_numeric(
        df["generation_kw"], errors="coerce"
    )
    df = df[df["account"].isin(PLANTS)].copy()
    return df

def get_control_files():
    files = list(CONTROL_DIR.rglob("*.xlsx")) + list(CONTROL_DIR.rglob("*.xls"))

    if not files and CONTROL_ZIP.exists():
        extracted = RAW / "control_extracted"
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(CONTROL_ZIP) as archive:
            archive.extractall(extracted)
        files = list(extracted.rglob("*.xlsx")) + list(extracted.rglob("*.xls"))

    return sorted(set(files))

def main():
    if not GENERATION_FILE.exists():
        raise FileNotFoundError(f"Generation file not found: {GENERATION_FILE}")

    generation = load_generation()
    control_files = get_control_files()
    if not control_files:
        raise FileNotFoundError(
            "No control workbooks found. Check data/raw/control or the control ZIP."
        )

    events = []
    errors = []

    for file_path in control_files:
        try:
            workbook = pd.ExcelFile(file_path)
        except Exception as exc:
            errors.append({"file": file_path.name, "error": str(exc)})
            continue

        for sheet in workbook.sheet_names:
            try:
                frame = pd.read_excel(
                    file_path, sheet_name=sheet, header=None, dtype=object
                )
            except Exception as exc:
                errors.append({
                    "file": file_path.name,
                    "sheet": sheet,
                    "error": str(exc),
                })
                continue

            values = [v for v in frame.to_numpy().flatten() if not pd.isna(v)]
            sheet_text = " | ".join(text(v) for v in values)
            lower_sheet = sheet_text.lower()

            # Require explicit evidence of curtailment.
            if not any(term in lower_sheet for term in [
                "curtail", "fully curtailed", "completely curtailed"
            ]):
                continue

            start_time, end_time = find_time_window(sheet_text)
            power_before = find_power_before_schedule(values)
            date = find_date(values, file_path.name, sheet)

            # Identify target plants from individual rows.
            for _, row in frame.iterrows():
                row_values = [v for v in row.tolist() if not pd.isna(v)]
                row_text = " | ".join(text(v) for v in row_values)
                account = find_account(row_text)
                if not account:
                    continue

                # Avoid emitting rows that are only plant inventory records.
                if not start_time and not end_time:
                    continue

                events.append({
                    "ac_number": account,
                    "plant_name": PLANTS[account],
                    "curtailment_date": date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_minutes": "",
                    "Power Before Schedule (kW)": power_before,
                    "data_source": f"{file_path.name} | {sheet}",
                    "source_evidence": row_text,
                    "review_status": "REVIEW_REQUIRED",
                })

    result = pd.DataFrame(events)

    if not result.empty:
        result = result.drop_duplicates(
            subset=["ac_number", "curtailment_date", "start_time", "end_time",
                    "data_source"]
        )

        def duration(row):
            if not row["start_time"] or not row["end_time"]:
                return ""
            start = pd.to_datetime(row["start_time"], format="%H:%M", errors="coerce")
            end = pd.to_datetime(row["end_time"], format="%H:%M", errors="coerce")
            if pd.isna(start) or pd.isna(end):
                return ""
            minutes = (end - start).total_seconds() / 60
            return int(minutes if minutes >= 0 else minutes + 1440)

        result["duration_minutes"] = result.apply(duration, axis=1)

        # Use generation timestamps to check whether readings exist in each
        # reported event window. Do not assume zero readings prove curtailment.
        result["generation_readings_in_window"] = 0
        for idx, event in result.iterrows():
            if not event["curtailment_date"] or not event["start_time"] or not event["end_time"]:
                continue
            account_rows = generation[generation["account"] == event["ac_number"]]
            if account_rows.empty:
                continue

            local_start = pd.Timestamp(
                f"{event['curtailment_date']} {event['start_time']}",
                tz="Asia/Colombo",
            ).tz_convert("UTC")
            local_end = pd.Timestamp(
                f"{event['curtailment_date']} {event['end_time']}",
                tz="Asia/Colombo",
            ).tz_convert("UTC")
            if local_end < local_start:
                local_end += pd.Timedelta(days=1)

            count = account_rows["timestamp"].between(
                local_start, local_end, inclusive="both"
            ).sum()
            result.loc[idx, "generation_readings_in_window"] = int(count)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)

    if errors:
        pd.DataFrame(errors).to_csv(
            DATA / "curtailment_extraction_errors.csv", index=False
        )

    print(f"Control workbooks scanned: {len(control_files)}")
    print(f"Candidate events extracted: {len(result)}")
    print(f"Output: {OUTPUT}")
    print("IMPORTANT: Review candidate rows before treating them as confirmed events.")

if __name__ == "__main__":
    main()
