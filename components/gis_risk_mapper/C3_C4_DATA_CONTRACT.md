# C3 → C4 prototype handover (CSV)

**File:** `components/gis_risk_mapper/output/c3_to_c4_risk_output.csv`

**Grain:** one row per transformer, uniquely identified by `(csc, sin)`. The rows are ordered by `priority_rank` (1 = highest *synthetic scenario-based exposure*). **Ranks may be tied** when rounded exposure scores are equal; C4 must not assume ranks are unique.

**Scope:** Real CEB transformer attributes combined with synthetic operating scenarios and a Random Forest model trained only on synthetic events. **Not observed reverse power flow, validated electrical risk, or approved curtailment instructions.** No `Loads.xlsx` values are used.

| Column | Meaning | Source |
|---|---|---|
| `csc`, `sin` | Compound transformer key | Real CEB |
| `feeder`, `gss` | Network area and feeder identification | Real CEB |
| `kva` | Transformer nameplate rating (kVA) | Real CEB |
| `solar_kw` | Installed rooftop solar capacity (kW) | Real CEB |
| `solar_to_kva` | Installed solar kW / nameplate kVA | Calculated from real CEB attributes |
| `exposure_score` | Synthetic *multi-day* exposure score; relative screening indicator, **not** a probability | Synthetic summary |
| `priority_rank` | Ordering by simulated exposure score (smaller rank = higher exposure) | Synthetic summary |
| `tier` | Provisional Low / Medium / High *synthetic exposure* category | Synthetic summary |
| `export_frequency` | Fraction of simulated hourly observations with a positive net-export condition, 0–1 | Synthetic summary |
| `peak_export_ratio` | Peak simulated net-export power / transformer kVA | Synthetic summary |
| `predicted_export_event` | 0/1 model classification of any simulated export between 11:00 and 14:00 on `prediction_date` | Synthetic model snapshot |
| `predicted_export_probability` | Classifier score for the **simulated** 11:00–14:00 event, 0–1; **not real-world risk probability** | Synthetic model snapshot |
| `prediction_date` | Date of the simulated ML prediction snapshot (not the export execution date) | Synthetic model snapshot |
| `data_basis` | Constant: `REAL_CEB_ATTRIBUTES_PLUS_SYNTHETIC_OPERATING_SCENARIOS` | Export metadata |

**Important integration boundaries:** `exposure_score`, `priority_rank`, `tier`, `export_frequency`, and `peak_export_ratio` summarize simulated conditions over many days. `predicted_export_probability` and `predicted_export_event` represent a *single simulated day*. Do not treat them as interchangeable or combine them in a curtailment rule without agreeing on their semantics. C4 must separately account for its own constraints and real operational data before recommending or triggering curtailment.

**Generation:** From the repository root, run `python components/gis_risk_mapper/predict_risk.py`, then `python components/gis_risk_mapper/export_c4.py`. The exporter checks duplicate `(csc, sin)` keys, row counts, probabilities/frequencies, required fields, consistent simulated date, and consistency of tied ranks with nearly equal exposure scores.

**Security:** The CSV includes restricted CEB transformer data. Do not commit the CSV, dashboard JSON, or private CEB raw files to a public Git repository, or deploy them publicly. Share only through your team's authorized channel. Share this schema document and exporter source in version control, subject to project policy.
