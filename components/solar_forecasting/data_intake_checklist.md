# CEB & Private Solar Plant Data Intake Checklist

This checklist must be executed immediately when raw time-series generation files arrive from the Ceylon Electricity Board (CEB) or private ground-mounted solar plant operators in the Embilipitiya / Southern / Sabaragamuwa region.

---

## 1. File Inventory & Header Inspection
- [ ] **File Format:** Are the files CSV, Parquet, or Excel (`.xlsx`)?
- [ ] **Number of Plants:** How many distinct solar plants are provided? (Target: At least 3–5 ground-mounted plants in Embilipitiya area).
- [ ] **File Size & Row Counts:** Expected ~525,600 rows per year for 1-minute data, or ~35,040 rows for 15-minute data per plant.
- [ ] **Sheet Architecture:** For Excel workbooks, identify metadata sheets vs generation sheets.

---

## 2. Time-Series Resolution & Timezone Verification
- [ ] **Sampling Frequency:**
  - 1-minute interval ($\Delta t = 60\text{ s}$) — Preferred for ramp detection.
  - 5-minute interval ($\Delta t = 300\text{ s}$) — Acceptable.
  - 15-minute interval ($\Delta t = 900\text{ s}$) — Standard for billing/forecasting, downsampled from 1-min.
- [ ] **Timestamp Format:** ISO 8601 string (`YYYY-MM-DD HH:MM:SS`), epoch, or split columns (`YEAR, MO, DY, HR, MIN`).
- [ ] **Timezone Specification:**
  - Explicitly confirm whether timestamps are in Sri Lanka Standard Time (`Asia/Colombo`, UTC+05:30) or `UTC`.
  - Check solar noon alignment: peak generation should occur around 12:05–12:20 PM SLST (or 06:35–06:50 UTC).
  - Convert and store internally strictly in `UTC`.

---

## 3. Mandatory & Optional Columns
- [ ] **Active Power Generation:**
  - Column name (e.g., `ActivePower_kW`, `P_MW`, `kW_Gross`, `Inverter_Output`).
  - Units verified: kW vs MW vs W. (Check if maximum observed value matches known plant capacity).
- [ ] **Plant Nameplate Capacity:**
  - DC Peak capacity ($P_{\text{dc\_peak}}$, MWp) and AC Inverter rating ($P_{\text{ac\_rating}}$, MW).
- [ ] **On-Site Weather Station Data (if available):**
  - Global Horizontal Irradiance (GHI, $\text{W/m}^2$)
  - Plane of Array Irradiance (POA, $\text{W/m}^2$)
  - Ambient Temperature ($T_{\text{amb}}$, $^\circ\text{C}$)
  - PV Module / Back-of-Module Temperature ($T_{\text{cell}}$, $^\circ\text{C}$)
  - Wind Speed ($v_{\text{wind}}$, $\text{m/s}$)
- [ ] **Grid Operational & Status Flags:**
  - Inverter status code (Running, Tripped, Standby, Grid Fault).
  - Curtailment signal / Setpoint limit (Active Power Curtailment instruction from CEB System Control Centre).

---

## 4. Continuity, Gaps, and Missingness Audit
- [ ] **Data Completeness:** Total observed records vs expected records across the date range.
- [ ] **Missing Share:** Flag if missing records exceed 5% overall or 2% during daylight hours.
- [ ] **Gap Distribution:**
  - Micro-gaps ($\le 3$ minutes): Can be linearly interpolated.
  - Meso-gaps (4 to 60 minutes): Must be flagged; lag features across gap must be reset.
  - Macro-gaps ($> 1$ hour): Treated as split segments; do not interpolate.
- [ ] **Zero / Negative Power Checks:**
  - Verify nighttime generation is exactly 0.0 or negligible auxiliary consumption ($-0.1$ to $-0.5\%$ capacity).
  - Check for non-physical negative values or stuck repeat values (sensor frozen).

---

## 5. Operational Masking Signals
- [ ] **Curtailment Instances:**
  - Identify intervals where power is flat-topped below clear-sky envelope during peak midday hours.
  - Apply $\pm 30$-minute safety buffer around each curtailment event.
- [ ] **Inverter Trips & Grid Outages:**
  - Identify sudden drops to 0 kW occurring when clear-sky GHI $> 400\text{ W/m}^2$.
- [ ] **Reconnection Ramps:**
  - Flag 600-second post-trip recloser delay and subsequent 900-second soft ramp-up. Exclude from natural ramp training set.

---

## 6. Ramp Event Census Across Threshold Grid
Run the automated intake validator (`src/ingest/validate_incoming_data.py`) to generate the empirical ramp frequency table across:
$$\Delta t \in \{1, 5, 10, 15\}\text{ min}, \quad r \in \{0.05, 0.10, 0.15, 0.20, 0.30\}$$
- [ ] Verify that at the primary operational threshold ($\Delta t = 10\text{ min}$, $r = 15\%$), ramp events represent between **1.0% and 5.0%** of daylight intervals (rare but statistically viable for machine learning).
- [ ] Check symmetry between Ramp-Up and Ramp-Down event frequencies.

---

## 7. Date Range & Seasonal Coverage
- [ ] **Evaluation Window:** Target April 1 to October 31 (capturing both the Southwest Monsoon transition and high-irradiance months).
- [ ] Ensure seamless overlapping dates with archived NWP forecast records (Open-Meteo / CAMS / NASA POWER).
