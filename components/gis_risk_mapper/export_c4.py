"""Export a validated C3 -> C4 CSV handover from the local dashboard JSON.

Run from the repository root:
    python components/gis_risk_mapper/export_c4.py

Reads:  components/gis_risk_mapper/output/transformer_risk.json
Writes: components/gis_risk_mapper/output/c3_to_c4_risk_output.csv

This file contains confidential real CEB transformer identifiers combined with
synthetic assessment results. Keep it private. No Loads.xlsx is used.
"""

import argparse
import csv
import json
import math
from pathlib import Path

C3_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = C3_DIR / "output"

COLUMNS = [
    "csc", "sin", "feeder", "gss", "kva", "solar_kw", "solar_to_kva",
    "exposure_score", "priority_rank", "tier", "export_frequency",
    "peak_export_ratio", "predicted_export_event",
    "predicted_export_probability", "prediction_date", "data_basis",
]


def require_number(value, field, transformer_id, low=None, high=None):
    if value is None or isinstance(value, bool):
        raise ValueError(f"{transformer_id}: missing/invalid {field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{transformer_id}: invalid {field}={value!r}") from exc
    if not math.isfinite(number) or (low is not None and number < low) or (high is not None and number > high):
        raise ValueError(f"{transformer_id}: {field} out of range: {value}")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=OUTPUT_DIR / "transformer_risk.json")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "c3_to_c4_risk_output.csv")
    args = parser.parse_args()

    with args.input.open(encoding="utf-8") as file:
        payload = json.load(file)

    meta = payload.get("metadata", {})
    if meta.get("data_basis") != "REAL_CEB_ATTRIBUTES_PLUS_SYNTHETIC_OPERATING_SCENARIOS":
        raise ValueError("Unexpected data basis: cannot hand off as the synthetic prototype")
    if meta.get("prediction_target") != "Any simulated net-export event between 11:00 and 14:00":
        raise ValueError("Unexpected prediction target")

    expected_date = meta.get("simulated_date")
    if not expected_date:
        raise ValueError("Missing simulated prediction date")

    transformers = payload.get("transformers", [])
    if not transformers or len(transformers) != meta.get("transformer_count"):
        raise ValueError("Transformer list missing or does not match metadata count")

    seen_keys = set()
    rows = []
    for item in transformers:
        csc, sin = item.get("csc"), item.get("sin")
        if not csc or not sin:
            raise ValueError("Transformer missing CSC or SIN")
        key = (str(csc), str(sin))
        transformer_id = "::".join(key)
        if key in seen_keys:
            raise ValueError(f"Duplicate transformer: {transformer_id}")
        seen_keys.add(key)

        summary = item.get("synthetic_summary") or {}
        prediction = item.get("synthetic_day_prediction") or {}
        if prediction.get("date") != expected_date:
            raise ValueError(f"{transformer_id}: prediction date differs from snapshot")

        tier = summary.get("tier")
        if tier not in {"Low", "Medium", "High"}:
            raise ValueError(f"{transformer_id}: unexpected exposure tier {tier!r}")

        event = prediction.get("predicted_export_event")
        if type(event) is not int or event not in (0, 1):
            raise ValueError(f"{transformer_id}: predicted_export_event must be 0 or 1")

        rank = summary.get("priority_rank")
        if type(rank) is not int or rank < 1:
            raise ValueError(f"{transformer_id}: invalid priority_rank")

        for field in ("feeder", "gss"):
            if item.get(field) in (None, ""):
                raise ValueError(f"{transformer_id}: missing {field}")

        row = {
            "csc": csc,
            "sin": sin,
            "feeder": item["feeder"],
            "gss": item["gss"],
            "kva": require_number(item.get("kva"), "kva", transformer_id, low=0.000001),
            "solar_kw": require_number(item.get("solar_kw"), "solar_kw", transformer_id, low=0),
            "solar_to_kva": require_number(item.get("solar_to_kva"), "solar_to_kva", transformer_id, low=0),
            "exposure_score": require_number(summary.get("exposure_score"), "exposure_score", transformer_id),
            "priority_rank": rank,
            "tier": tier,
            "export_frequency": require_number(summary.get("export_frequency"), "export_frequency", transformer_id, low=0, high=1),
            "peak_export_ratio": require_number(summary.get("peak_export_ratio"), "peak_export_ratio", transformer_id),
            "predicted_export_event": event,
            "predicted_export_probability": require_number(prediction.get("predicted_export_probability"), "predicted_export_probability", transformer_id, low=0, high=1),
            "prediction_date": expected_date,
            "data_basis": meta["data_basis"],
        }
        rows.append(row)

    # Equal exposure scores can legitimately produce tied priority ranks.
    # Each transformer is still uniquely identified by (csc, sin), checked above.
    rank_to_score = {}
    tied_rank_rows = 0
    for row in rows:
        rank = row["priority_rank"]
        score = row["exposure_score"]
        if rank in rank_to_score:
            tied_rank_rows += 1
            if not math.isclose(rank_to_score[rank], score, rel_tol=0, abs_tol=0.0002):
                raise ValueError(
                    f"Rank {rank} shared by transformers with different exposure "
                    f"scores ({rank_to_score[rank]} vs {score}); check ranking logic"
                )
        else:
            rank_to_score[rank] = score

    # Deterministic order, without changing the source ranking or inventing ranks.
    rows.sort(key=lambda row: (row["priority_rank"], str(row["csc"]), str(row["sin"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print("C3 -> C4 CSV created successfully")
    print("Transformers:", len(rows))
    print("Additional transformers sharing a rank:", tied_rank_rows)
    print("Prediction date (synthetic):", expected_date)
    print("Simulated positive predictions:", sum(row["predicted_export_event"] for row in rows))
    print("File:", args.output.resolve())
    print("CAUTION: Contains real CEB attributes and synthetic results; share only with authorized team members.")


if __name__ == "__main__":
    main()
