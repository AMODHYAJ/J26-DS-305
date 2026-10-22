# Proposal requirements to implementation

Authority: complete IT23177000 proposal (43 pages), objectives pp.18–19, methods/benchmarks pp.20–23, integration pp.27–30, functional/non-functional requirements pp.31–33. The supplied instructions add operational safeguards, naming and execution requirements. No metric target is claimed achieved solely because the proposal requests it.

| Requirement | Implemented evidence | Remaining evidence gap |
|---|---|---|
| Billing/net-metering and monthly consumption integration | `C2_TLA_ingest.py` audits supplied account/capacity registers and database; `C2_TLA_adapters.py` validates separately supplied interval import/export energy and monthly billing semantics | Supplied files contain no usable measured billing/gross-consumption labels; unverified totals are excluded from inference |
| Historical feeder and transformer demand | Actual GSPL quarter-hour MW loader; static Loads and all Access tables audited; exact SectionId static adapter | No measured transformer time series; static allocations/defaults are labelled accordingly |
| C1 solar forecasts | Validated exact-key kW-to-MW forecast adapter; explicit CSI×clear-sky-AC conversion helper; independent daylight-profile substitute | No live C1 feeder-power service, validated AC conversion reference or measured PV forecast errors |
| Feature engineering and hidden XGBoost model | `C2_TLA_model.py`, inference-available numeric/calendar features, chronological train/calibration/test, training-only imputation | Synthetic latent targets; no real-world supervised validation |
| True/residual/hidden demand | `C2_TLA_core.py`, signed net, arithmetic balance, explicit boundary/loss assumption, zero/missing handling | Non-solar generation/storage and meter error not observed |
| Demand visibility and hidden peaks | Uncapped VLI with undefined-denominator handling; selected-window peak and reverse-flow flags; hidden threshold crossings | Thresholds and operational interpretation require CEB approval |
| SHAP individual/global explanation | Native exact Tree SHAP, package cross-check, additivity tests, separate physical correction, UI local/global views | Explanations describe the synthetic-trained estimator, not measured causal relationships |
| Benchmarks and metrics (proposal Table 2) | Apparent, direct-addition, historical profile, XGBoost; MAE/RMSE/R²/MAPE, daily peak magnitude/timing, scenarios and empirical calibration coverage | Scores are synthetic only; expert score awaits completed review template |
| Historical/scenario/expert validation | CEB consistency/night/energy checks, profile/capacity sensitivity controls, scenario metrics; review CSV | Independent field validation and external supervisor review pending |
| Curves and DCC usability | React/Recharts workbench matching the C3 design; functioning defaults, feeder/date/method/source controls, demand/solar/VLI/quality views, SHAP, evidence and downloads | Verified through API tests and real Chrome checks; field operator/expert review remains pending |
| C4 demand-threshold interface | Typed FastAPI `/v1/reconstruct`, version c2.tla.v1, signed MW and aware timestamps | Teammate C4 implementation has no C2 consumer; no integration-complete claim |
| ~5-second updates and year history | Vectorized in-memory reconstruction and explicit performance probe; cached raw ingestion | Full source parsing/audit is slower; hardware-dependent performance results are documented, not assumed |
| Secure data and communications | Local-only binding, optional required Bearer token, ignored private data, no unsafe pickle loading | Remote TLS, secret management and CEB governance deployment remain external |
| Repeatability and reliability | Seeded simulation, saved UBJ/schema/metadata/split dates, CPU defaults, Windows command launchers, tests and lock file | Time-series uncertainty transfer and additional regions need future research |

No database defaults or synthetic records are promoted to measured evidence to satisfy an unavailable input requirement. This component runs independently while preserving those research limitations.
