# Component 2 — True Load Analysis

Working local research component for the 43-page **IT23177000** proposal, particularly §§2–5 (pp.18–33). The primary workflow reconstructs CEB feeder-boundary demand from measured net MW and an explicitly assumed PV profile derived from real capacity registers. A separate XGBoost experiment uses simulated latent PV targets and Tree SHAP. Neither provides independent CEB true-demand accuracy.

## Windows commands

The interface is now **React + Recharts**, matching the C3 dashboard's charcoal/lime design on main. FastAPI serves both the built React UI and the research endpoints on one local origin. The Streamlit entry point was removed; research calculations and saved models are preserved.

Run from the repository root in PowerShell. Fresh setup needs **Python 3.12 x64** (with the Python launcher) and **Node.js 24 LTS** for the frontend build. This laptop has ignored portable runtimes under `C2_TLA_tools`; scripts detect them automatically. Once built, serving the UI requires Python only. No activation, execution-policy change, GPU, WSL or Docker is required.

```powershell
.\components\C2_TLA_true_load_analysis\C2_TLA_setup.cmd

# Extract the supplied archive OUTSIDE the repository; keep its filenames unchanged.
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\CEB_data.zip" -DestinationPath "$env:TEMP\C2_TLA_raw"
$env:C2_TLA_CEB_PATH = "$env:TEMP\C2_TLA_raw\CEB_data"

# Real ingestion, seeded training, evaluation, and complete Excel/CSV/Access audit:
.\components\C2_TLA_true_load_analysis\C2_TLA_launch.cmd all --ceb-path "$env:C2_TLA_CEB_PATH"

.\components\C2_TLA_true_load_analysis\C2_TLA_launch.cmd ui
# Open http://127.0.0.1:8502
# API docs are served by the same process: http://127.0.0.1:8502/docs

# Optional separate API process; not needed for the UI:
.\components\C2_TLA_true_load_analysis\C2_TLA_launch.cmd api
# API docs: http://127.0.0.1:8002/docs

.\components\C2_TLA_true_load_analysis\C2_TLA_launch.cmd test

# Rebuild after changing React sources:
.\components\C2_TLA_true_load_analysis\C2_TLA_launch.cmd build-ui
```

Set `C2_TLA_CEB_PATH` in each terminal that needs private data. Without it, portable tests explicitly skip the two real-input checks. The UI starts with a working synthetic example when no CEB inputs/cache are present; its source selector labels this visibly. Selecting CEB with invalid inputs displays an error and never switches to synthetic.

Individual commands: `prepare` recreates the demo model and synthetic evidence (120 days, seed 23177000); `ceb --ceb-path "..."` refreshes measured-input estimates; `audit --ceb-path "..."` scans every input. `all` additionally derives simulation demand magnitude from the median absolute nontrivial CEB net MW. This scale informs simulation only, not training labels. On a fresh machine the Access audit requires the matching Microsoft Office ACE OLEDB provider. If unavailable, the audit records the exact error; Excel-based reconstruction and the rest of the component still run. This laptop's Office provider was successfully used read-only.

## Files and output

All project-owned files/directories start with `C2_TLA_`. Imports use the component directory on `PYTHONPATH`, without `__init__.py`. The launcher sets this path. `components/demand_analyzer` on main was only `.gitkeep`; it is preserved. A historical teammate branch contains an unused kWh/"kW" direct decomposition; it is neither imported nor copied because its unit/self-consumption assumptions are unsuitable.

`C2_TLA_outputs/` holds private local CSVs and full audit JSON, all ignored. `C2_TLA_models/` holds reproducibly generated UBJ, metadata and evaluation JSON, also ignored. `C2_TLA_demo/` contains a small portable synthetic model and metadata for immediate model loading. No pickle/joblib is loaded. Raw CEB inputs, account records, credentials, caches and runtimes are excluded from commits.

React sources and prefixed npm manifest/lock/config live in `C2_TLA_frontend/`. `C2_TLA_build_ui.py` creates an ignored npm workspace under `C2_TLA_tools/C2_TLA_react_build`, where conventional tool-managed `package.json`, `package-lock.json` and `node_modules` stay local. Vite outputs prefixed production assets to ignored `C2_TLA_web/`; setup builds them reproducibly. The launcher builds missing assets before serving. The default port is 8502; override with `C2_TLA_UI_PORT` if needed. No external CDN or teammate service is needed at runtime.

The UI provides Overview, Demand analysis, Explanations and Research evidence. Source, feeder, method and local dates are selected in the filter panel. The expandable assumptions panel contains the CEB path, threshold and sensitivity controls. CSV/JSON export always uses the displayed selection. All chart timestamps use Asia/Colombo explicitly.

Optional real-browser checks use installed Chrome:

```powershell
# Install optional testing dependency into your chosen Python environment:
.\.venv\Scripts\python.exe -m pip install -r components\C2_TLA_true_load_analysis\C2_TLA_browser_requirements.txt
.\.venv\Scripts\python.exe components\C2_TLA_true_load_analysis\C2_TLA_tests\C2_TLA_browser_check.py --ceb-path "$env:C2_TLA_CEB_PATH"
```

On this laptop, use `C2_TLA_tools\C2_TLA_python\python.exe` instead of `.venv\Scripts\python.exe`. Browser screenshots and check results stay in ignored outputs.

Start with [the data investigation](C2_TLA_docs/C2_TLA_data_findings.md), [research methods](C2_TLA_docs/C2_TLA_methodology.md), [integration contract](C2_TLA_docs/C2_TLA_integration.md), [requirements mapping](C2_TLA_docs/C2_TLA_requirements_mapping.md), and [verification evidence](C2_TLA_docs/C2_TLA_verification.md).

## Interpretation and limitations

All interval active power is **MW**; interval energy is **MWh**; capacity-register kW is divided by 1000. A feeder net-import boundary reconstructs gross downstream demand **including downstream losses**. It does not isolate end-use consumption or customer PV self-consumption. Other generation, storage and measurement errors are unobserved. The supplied curtailment image confirms other generation exists, so the PV-only balance is conditional.

The capacity-to-telemetry crosswalk is explicit but provisional. Telemetry sign, scale, capacity effective dates and boundary completeness require CEB review. F6–F8 have near-zero channels; F1/F4 include export exceeding the assumed PV envelope. Outputs retain these contradictions rather than modifying observations. Historical capacity snapshots are applied as static sensitivity assumptions, not claimed commissioning histories.

The API and UI bind to loopback. Set `C2_TLA_API_TOKEN` to require Bearer authentication on reconstruction and workbench requests; React presents a token-entry form when required, keeping it in browser session storage. Remote deployment additionally requires TLS and a managed access policy. No live C1 power forecast or C4 consumer is available on main; adapters and contract tests are present, but team integration and operational validation remain outstanding.
