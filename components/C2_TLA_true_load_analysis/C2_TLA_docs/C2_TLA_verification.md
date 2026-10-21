# Executed verification — 2026-10-21

Environment: Windows, Python 3.12.10 x64, CPU-only XGBoost with two threads. Exact installed versions are recorded in `C2_TLA_lock.txt`; the documented setup launcher was executed successfully. No system-wide execution-policy/security changes were made. The ignored local Python runtime substitutes for `.venv` on this laptop because no usable Python installation was initially on PATH.

## Automated checks

`C2_TLA_launch.cmd test` was executed with `C2_TLA_CEB_PATH` set to the supplied extracted files. The suite contains **19 tests**, including parameterized invalid-input cases. It covers signed/zero/missing/non-finite demand, units and aware timestamps, duplicates and joins, electrical balance, VLI reverse-flow/denominator behavior, thresholds and irregular intervals, night/energy checks, deterministic cloud/penetration/missing-data simulation, chronological split isolation and training-only medians, inference schema and target-feature exclusion, UBJ save/reload, physical correction and SHAP additivity, SHAP-package/native consistency, API validation/authentication, real CEB loader/register reconciliation, CSV/JSON round trips, portable demo reload, and both Streamlit modes.

Streamlit AppTest verified source switching, XGBoost selection, feeder selection, rendered charts, explanation/model status, two download controls, invalid-path errors and near-zero telemetry warnings. The earlier source-switch date-state defect was fixed and the affected tests passed. Verification used application testing, **not a visual browser review**; CSS layout and browser-specific rendering still merit human review.

Final run result: **19 passed, one upstream deprecation warning, 129.59 seconds**. The subsequent complete `all` command also exited successfully, auditing 11 files and 99 Access tables. Final combined ingestion/reconstruction took 28.86 seconds under concurrent verification load; training, prediction and explanations took 33.65 seconds.

The dependency stack emits one upstream Starlette deprecation warning about its HTTPX TestClient transport. API tests pass; no dependency warnings are suppressed.

## Executed pipelines and data audit

The actual CEB and synthetic training/evaluation pipelines ran, including model saving/reloading and explanation generation. Full local logs: `C2_TLA_outputs/C2_TLA_pipeline_run.txt` and `C2_TLA_outputs/C2_TLA_test_run.txt`. Private machine-readable results and full audit stay ignored. The audit covers **11 input files, 91 worksheets and 99 Access user tables**. Office ACE was invoked read-only. A sandbox-nested invocation timed out; the directly completed audit was reused only after verifying the database SHA-256. The code now records provider errors/timeouts instead of blocking the other analytical outputs indefinitely.

Actual telemetry: **88,320** Embilipitiya feeder MW intervals; **61,824** intervals reconstructed on seven capacity-matched feeders, 2026-07-01 through 2026-09-30. No independent true-demand labels exist. Direct reconstruction's maximum floating balance error was **6.66e-16 MW**; night difference was zero. Left-held energy totals were net **18,267.385 MWh**, estimated PV **12,058.582 MWh**, reconstructed demand **30,325.967 MWh**, with zero reconciliation error and each of seven final unbounded intervals excluded. These demonstrate arithmetic consistency, not true-demand accuracy.

Capacity summary/detail totals agree at 29,650.47 kW; all 390 composite transformer groups reconcile within 0.05 kW after handling the report's moving CSC field. Legitimate negative readings and suspicious near-zero channels are retained. No raw source files were renamed or edited.

## Synthetic benchmark evidence

The included portable demo uses 120 days, demand scale 4 MW, seed 23177000, three penetration levels, clouds, forecast error, occasional hidden midday peaks, missing/zero measurements and chronological 60/20/20 partitions. Its held-out scores are:

| Method | MAE MW | RMSE MW | R² | MAPE % | Daily peak timing MAE min |
|---|---:|---:|---:|---:|---:|
| Apparent | 0.7310 | 1.3714 | −1.1426 | 22.8877 | 34.38 |
| Direct addition | 0.1393 | 0.3273 | 0.8780 | 4.3487 | 25.42 |
| Historical profile | 0.3068 | 0.4787 | 0.7389 | 9.0129 | 64.38 |
| XGBoost | 0.0754 | 0.1866 | 0.9603 | 2.2899 | 9.17 |

Observed-input methods have n=6,885 after missing net observations; the historical method has n=6,912. Empirical latent-hidden interval coverage is **89.05%** at nominal 90%. These scores refer to the explicitly simulated targets in `C2_TLA_demo/C2_TLA_evaluation.json`. `all` generates another local simulation scaled from CEB characteristics; those separately saved scores can differ. The simulator's biased forecast is learnable, so its advantage does not establish an operational XGBoost advantage. No CEB accuracy score or expert-validation score is fabricated.

## Services, performance and repository checks

Both servers were launched. HTTP requests to Streamlit `/_stcore/health`, FastAPI `/health` and `/openapi.json` returned 200. A real HTTP POST to `/v1/reconstruct` using the labelled mock and XGBoost returned validated output with units, timezone, provenance, reverse-flow VLI and quality flags. Health correctly reported model loaded and live C1/C4 integrations absent.

One-year in-memory reconstruction of **105,120 rows** (three feeders × 365 days × 96 intervals) took **1.58 seconds** after vectorizing quality flags. A real-source optimized ingestion probe processed 61,824 rows in **19.41 seconds**. Initial unoptimized source reads took 58–92 seconds. These are separate from the approximately five-second updated-input reconstruction target; full workbook audit and training are offline operations. Performance is hardware/load dependent and no production latency SLA is claimed.

Naming, ignored outputs/raw data, staged file types and `git diff --check` were inspected. The portable demo is approximately 182 KB. Only the new prefixed component tree and a minimal shared `.gitignore` change are intended for commits. Main remains unmerged; no teammate implementation was overwritten. External limitations: approved crosswalk/telemetry scale, generation/storage coverage, independent measured labels, expert review, live C1 power forecasts and a C4 C2-output consumer.
