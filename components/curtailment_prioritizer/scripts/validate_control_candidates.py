
from pathlib import Path
import re
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"

INPUT_FILE = ARTIFACTS / "control_record_candidates.csv"
OUTPUT_FILE = ARTIFACTS / "control_candidate_triage.csv"
SUMMARY_FILE = ARTIFACTS / "control_candidate_triage_summary.csv"

TARGETS = {
    "6470900542": ["laugfs solar", "laugfs power"],
    "6470900534": ["irish & eco solar", "irish and eco solar"],
    "6470900607": ["dimo solar", "thunkama"],
    "6470900828": ["chandrikawewa"],
    "6470900836": ["kiriibbanwewa"],
}

# These terms suggest an actual curtailment record, but do not
# independently prove that a curtailment event occurred.
CONFIRMED_TERMS = [
    "completely curtailed",
    "fully curtailed",
    "fully curtail",
    "partially curtailed",
    "partially curtail",
    "curtailment from",
    "curtailed from",
    "curtailment started",
    "curtailment start",
    "curtailment ended",
    "curtailment end",
]

AMBIGUOUS_TERMS = [
    "managed by nscc",
    "nscc",
    "curtail",
    "solar",
]

NON_EVENT_TERMS = [
    "total curtailment",
    "curtailment summary",
    "curtailment target",
    "curtailment plan",
    "curtailment schedule",
]


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def find_target(text):
    """Return a target account number only when its identity is explicit."""
    text = text.lower()
    matches = []

    for account, aliases in TARGETS.items():
        if account in text or any(alias in text for alias in aliases):
            matches.append(account)

    return ";".join(sorted(set(matches)))


def detect_date(text):
    """Find date-like strings; these still require validation."""
    patterns = [
        r"\b\d{4}[./-]\d{1,2}[./-]\d{1,2}\b",
        r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
        r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return ""


def detect_time_range(text):
    """Detect explicit time ranges without assuming a duration."""
    patterns = [
        r"\b\d{1,2}:\d{2}\s*(?:AM|PM)?\s*(?:to|-|–|until)\s*"
        r"\d{1,2}:\d{2}\s*(?:AM|PM)?\b",
        r"\bfrom\s+\d{1,2}:\d{2}\s*(?:AM|PM)?\s+"
        r"to\s+\d{1,2}:\d{2}\s*(?:AM|PM)?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)

    return ""


def classify(row):
    row_text = clean(row.get("row_text", ""))
    cell_values = clean(row.get("cell_values", ""))
    context = clean(row.get("sheet_top_rows", ""))

    # Search cell values and row text for evidence. Context is retained
    # for review, but cannot by itself confirm an event.
    text = f"{row_text} | {cell_values}"
    lower = text.lower()

    target = find_target(text)
    date = detect_date(text)
    time_range = detect_time_range(text)

    strong_terms = [
        term for term in CONFIRMED_TERMS if term in lower
    ]
    ambiguous_terms = [
        term for term in AMBIGUOUS_TERMS if term in lower
    ]
    summary_terms = [
        term for term in NON_EVENT_TERMS if term in lower
    ]

    if summary_terms and not strong_terms:
        classification = "REVIEW"
        reason = "Possible summary, plan, or schedule rather than an event."

    elif not target:
        classification = "REJECT_OR_REVIEW"
        reason = "No explicit target plant identity found in this row."

    elif strong_terms and date and time_range:
        classification = "HIGH_PRIORITY_REVIEW"
        reason = (
            "Target plant, event-like wording, date, and time range found. "
            "Verify against the source workbook before confirmation."
        )

    elif strong_terms and date:
        classification = "REVIEW"
        reason = (
            "Target plant, event-like wording, and date found; "
            "time range or duration is missing."
        )

    elif strong_terms:
        classification = "REVIEW"
        reason = (
            "Event-like wording found, but a usable date was not detected."
        )

    elif ambiguous_terms:
        classification = "REVIEW"
        reason = (
            "Relevant keyword found, but this row does not establish "
            "a confirmed curtailment event."
        )

    else:
        classification = "REJECT_OR_REVIEW"
        reason = "Insufficient evidence of a curtailment event."

    return pd.Series({
        "detected_account_number": target,
        "detected_date_text": date,
        "detected_time_range": time_range,
        "event_like_terms": "; ".join(strong_terms),
        "ambiguous_terms": "; ".join(ambiguous_terms),
        "triage_classification": classification,
        "triage_reason": reason,
        "sheet_context": context,
    })


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Candidate file not found: {INPUT_FILE}\n"
            "Run extract_control_records.py first."
        )

    df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")

    if df.empty:
        print("Candidate file is empty. Nothing to validate.")
        return

    results = df.apply(classify, axis=1)
    output = pd.concat([df, results], axis=1)

    # Preserve all rows, including rejected or ambiguous ones, so that
    # the classification can be audited and improved.
    output.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    summary = (
        output.groupby(
            "triage_classification",
            dropna=False,
        )
        .size()
        .reset_index(name="row_count")
        .sort_values("row_count", ascending=False)
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("=" * 60)
    print("CONTROL CANDIDATE TRIAGE SUMMARY")
    print("=" * 60)
    print(f"Candidate rows processed: {len(output)}")
    print("\nClassification counts:")
    print(summary.to_string(index=False))
    print(f"\nDetailed triage: {OUTPUT_FILE}")
    print(f"Summary:         {SUMMARY_FILE}")
    print(
        "\nIMPORTANT: These classifications are automated screening results, "
        "not confirmed curtailment events."
    )


if __name__ == "__main__":
    main()
