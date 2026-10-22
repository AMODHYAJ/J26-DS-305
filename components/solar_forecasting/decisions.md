# Component 1 (Solar Forecasting & Ramp Event Detection) — Architecture & Decisions Record

## 1. Context & Scope
Component 1 is responsible for:
1. **Solar Power Forecasting:** Multi-horizon forecast (15 min to 4 hours) of clear-sky index ($k_t$) and active power ($P_t$) at plant level, aggregated to primary distribution feeders.
2. **Solar Ramp Event Detection:** Probabilistic detection of significant ramp-rate events ($+\Delta P$ or $-\Delta P$) within upcoming decision windows (15 to 30 minutes), surpassing deterministic forecast slope baselines.
3. **BESS Operational Support:** Providing headroom metrics and reserve dispatch recommendations to mitigate severe ramp violations without breaching battery SoC boundaries.

---

## 2. Temporal & Coordinate Conventions
* **Internal Modeling & Storage Timezone:** **UTC (Coordinated Universal Time)**
  - All time-series data timestamps in raw, processed, model inputs, and model outputs are strictly aligned to UTC.
  - This eliminates daylight-saving discontinuities and ensures exact astronomical solar geometry synchronization with `pvlib`.
* **User-Facing / Logging Timezone:** **Asia/Colombo (UTC+05:30)**
  - All logs, dashboard views, API response display fields, and human reports convert UTC timestamps to Asia/Colombo standard time.
* **Geographical Anchors (4 CSCs in Embilipitiya Region):**
  - Derived from Component 3's GIS node centroids (`Gnodes.xlsx` Kandawala EPSG:5234 converted to WGS84 EPSG:4326):
    1. **`emb` (Embilipitiya CSC):** `6.30786° N, 80.85806° E` (125 transformers, 12,924.8 kW rooftop solar)
    2. **`god` (Godakawela CSC):** `6.51197° N, 80.69227° E` (88 transformers, 5,976.4 kW rooftop solar)
    3. **`kol` (Kolonna CSC):** `6.36618° N, 80.70113° E` (52 transformers, 2,900.5 kW rooftop solar)
    4. **`uda` (Udawalawa CSC):** `6.39983° N, 80.85726° E` (92 transformers, 6,142.9 kW rooftop solar)
* **Weather Resolution & Multi-Location Ingestion:**
  - **NASA POWER Coarseness:** NASA POWER operates on a coarse ~0.5° × 0.625° grid (~55 km × 70 km). All 4 CSCs (10 to 29 km apart) fall within the same or neighboring MERRA-2 cell, resulting in identical irradiance numbers. Furthermore, NASA POWER suffers from latency (-999 missing data from Aug 1 to Oct 16, 2026).
  - **Open-Meteo & CAMS:** Ingested separately per `location_id` (`emb`, `god`, `kol`, `uda`). Empirical analysis confirms that while clear-sky irradiance is virtually identical (<1% diff), cloud cover differs significantly (correlation between `emb` and `god` is 0.768, with maximum daylight GHI differences reaching 384 W/m²).
* **Plant Locations vs Component 3 Rooftop Transformers:**
  - Files `EMB-*`, `Gnodes.xlsx`, and `transformers_solar.csv` represent **distribution transformer rooftop solar** (357 transformers, 27.94 MW total), NOT utility-scale ground-mounted plants.
  - Google Maps pins are unverified supplier/business addresses or proposed/unbuilt sites (e.g. Chandrika Weva, Samanalawewa) and are excluded from scientific training data. Authoritative plant SCADA logs are pending from CEB NSCC.

---

## 3. Data Ingestion & Quality Masking Rules
To ensure realistic models and eliminate spurious data artifacts:
1. **Solar Elevation Cutoff:**
   - Daylight records only: Solar elevation $\theta_{\text{elev}} \ge 10^\circ$ (zenith angle $\theta_z \le 80^\circ$).
   - Low sun angles ($\theta_{\text{elev}} < 10^\circ$) cause division by near-zero clear-sky irradiance and optical scattering anomalies.
2. **Curtailment Masking:**
   - When a plant's active power is capped by the grid operator below its clear-sky potential while irradiance is high, the interval is masked out with a **$\pm 30$-minute safety margin**.
3. **Grid Trips & Inverter Outages:**
   - Generation dropping abruptly to zero or near-zero while clear-sky irradiance exceeds $400\text{ W/m}^2$ is treated as a plant/grid outage rather than meteorological ramp.
4. **Reconnection & Reclosers:**
   - Following an outage restoration, grid code mandates a **600-second stabilization delay** followed by a ramp rate limit (typically **900 seconds** to full power). These reconnection ramp-ups are masked from natural weather ramp training.
5. **Missing Data & Interpolation:**
   - Small gaps $\le 3\text{ minutes}$ are linearly interpolated. Gaps $> 3\text{ minutes}$ are kept as `NaN` and dropped from continuous feature lag windows.

---

## 4. Solar Forecasting Parameters (Stage 1)
* **Target Variable:** Clear-Sky Index ($k_t$)
  $$k_t = \frac{P_t}{P_{\text{cs}}(t)}$$
  Where $P_{\text{cs}}(t)$ is the theoretical clear-sky plant output computed via `pvlib` (Ineichen clear-sky GHI $\times$ calibrated plant capacity factor).
  Forecasting $k_t$ removes the diurnal astronomical cycle, stabilizing model variance.
* **Forecast Horizons ($H$):**
  - **15 minutes** (Fast tertiary dispatch)
  - **30 minutes** (Sub-hourly reserve management)
  - **60 minutes** (Hourly balancing)
  - **120 minutes** (2-hour lookahead)
  - **240 minutes** (4-hour lookahead)
* **Model Hierarchy:**
  1. *Baseline 1:* Raw Persistence ($P_{t+H} = P_t$)
  2. *Baseline 2:* Smart Persistence ($k_{t+H} = k_t \implies \hat{P}_{t+H} = k_t \times P_{\text{cs}, t+H}$) — Primary Benchmark
  3. *Baseline 3:* Ridge Regression
  4. *Main Model:* Pooled LightGBM Regressor across all plants with static plant features (Capacity, Tilt, Azimuth, Performance Ratio).
* **Cross-Validation & Splitting:**
  - **Chronological Split:** 70% Train, 15% Validation, 15% Test.
  - **Leave-One-Plant-Out (LOPO):** Train on $N-1$ regional plants, test out-of-sample on the $N$-th plant to evaluate regional generalization.

---

## 5. Solar Ramp Event Detection Parameters (Stage 2)
* **Event Formulation:**
  A ramp event occurs when the normalized power rate of change over duration $\Delta t$ exceeds threshold $r$:
  $$\Delta P_{\text{norm}}(\Delta t) = \frac{P_t - P_{t-\Delta t}}{P_{\text{rated}}}$$
  - **Ramp-Down Event:** $\Delta P_{\text{norm}}(\Delta t) \le -r$
  - **Ramp-Up Event:** $\Delta P_{\text{norm}}(\Delta t) \ge +r$
* **Exploration Grid:**
  - $\Delta t \in \{1, 5, 10, 15\}\text{ minutes}$
  - $r \in \{0.05, 0.10, 0.15, 0.20, 0.30\}$ (i.e., 5% to 30% of capacity)
  - *Data-derived rate (Logothetis 2022):* 95th/99th percentile of empirical clear-sky normalized rate of change.
* **Primary Operational Setting:**
  - Ramp duration: $\Delta t = 10\text{ minutes}$
  - Ramp magnitude threshold: $r = 0.15$ (15% capacity swing in 10 minutes)
  - Lookahead alert window: $H = 30\text{ minutes}$ ($Y_{t}=1$ if a ramp onset occurs at any $t' \in [t+1, t+H]$)
* **Models & Decision Calibration:**
  - *Baselines:* Deterministic slope rule ($\Delta \hat{P}_{\text{forecast}}/\Delta t \ge r$), Persistence rule.
  - *Main Model:* LightGBM Classifier with class weighting (`is_unbalance=True`).
  - *Threshold Tuning:* Threshold set on validation set to maximize F1 while securing operational recall $\ge 85\%$.
  - *Calibration:* CalibratedClassifierCV (isotonic / sigmoid) to output true posterior event probabilities.
* **Defensible Verification:**
  - Paired bootstrap testing ($B=1,000$ iterations) with 95% confidence intervals on $\Delta\text{F1}$ and $\Delta\text{PR-AUC}$ against deterministic baselines.
  - NWP Error Propagation study: perturb weather inputs by $\pm 10\%$ and random noise, re-extract features, and measure degradation.
  - Explainability: SHAP TreeExplainer feature attribution for top warning events.

---

## 6. Feeder-Level Aggregation & BESS Integration
* **Feeder Aggregation:**
  Using the CEB transformer data from Embilipitiya GSS feeders (`EMB-EMB.xlsx`, `EMB-GOD.xlsx`, `EMB-KOL.xlsx`, `EMB-UDA.xlsx`), total rooftop capacity per transformer $j$ is scaled:
  $$\hat{P}_{\text{feeder}}(t+H) = \sum_{j \in \mathcal{T}_{\text{feeder}}} \text{Cap}_j \times \hat{k}_{t+H} \times \text{PR}_j \times \frac{G_{\text{cs}}(t+H)}{1000}$$
* **BESS Parameters:**
  - Scaled from CEB pilot BESS specifications (Anuradhapura & Galle): 500 kWh capacity, 250 kW power (0.5C rate), 88% roundtrip efficiency, SoC operational bounds $[10\%, 90\%]$.
  - Dynamic reserve rules based on ramp probability alerts.
