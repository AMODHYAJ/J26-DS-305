# Research methodology and evidence boundaries

## Electrical balance

At a feeder import meter, `N = D + losses − PV − other_generation + storage_charge − storage_discharge`. The implemented PV-only estimate is `T_hat = N + PV_hat`, conditional on other terms being absent/negligible or unchanged. Consequently T_hat includes losses. Hidden demand H_hat denotes the PV contribution masking feeder demand, not independently identified behind-the-meter self-consumption. Residual `R_hat = T_hat − PV_hat`. Direct addition gives `R_hat = N` identically. XGBoost gives `R_hat = N + H_model − PV_hat`; its difference from N is exposed, not treated as a new measurement.

No clipping of negative measured N or inconsistent negative reconstructed T is performed. Missing N remains missing even when the model can estimate H. VLI = H/T for T > 1e-6 MW; otherwise null with a quality flag. Reverse flow can give VLI > 1; the index is uncapped. Thresholds compare T to an operator-selected positive MW threshold and distinguish hidden crossings (N at/below threshold, T above). Missing T has `threshold_status=unknown_missing_measurement`. Peaks flag maxima within the selected feeder/window, including ties; they are not independently verified peaks.

## Real-input estimation

CEB's GSPL workbook provides 96 quarter-hour columns per day. Full sheet metadata, not truncated sheet names, selects Embilipitiya feeder MW channels. AMP, substation totals, hydro generation and daily summary fields are not mixed into those channels. Local export dates contain no offset; Asia/Colombo is an explicit interpretation based on CEB's Sri Lankan study area and local daily labels. UTC is used for joins; outputs retain equivalent aware timestamps.

The deterministic solar profile is `C × d × max(0, sin(pi × (local_hour−6)/12))` during 06:00–18:00, zero otherwise. Default d=0.8 approximates combined AC conversion/yield losses. It is physically motivated by daylight and bounded installed capacity, but has no weather, orientation, curtailment or validated sunrise model. Limits 0.35 and 1.0 times C×daylight are sensitivity bounds, **not** confidence quantiles. A capacity multiplier supports penetration sensitivity. A real C1 power forecast may replace this estimator through exact validated joins. CSI requires a separately justified feeder clear-sky AC MW reference; CSI alone cannot establish generation.

## Supervised experiment

No independent measured hidden-demand/true-demand targets exist in the supplied evidence. XGBoost is trained on a simulator's latent PV MW. Its net demand derives from independent morning/evening consumption curves, weekday effects, occasional industrial midday peaks, PV penetration 0.4/1/2 times demand scale, stochastic daily weather, intraday cloud variation, multi-hour cloudy spells, measurement gaps/zeros and biased noisy forecasts. Scale defaults to 4 MW for portable setup; `all` uses actual nontrivial CEB absolute net-demand median. Seed 23177000 and all split dates/configuration are saved. Synthetic targets are never called measured ground truth.

Features available at interval inference: current observed net MW, PV forecast MW, known installed capacity MW, sine/cosine of local clock and day of week. No future values, full-data statistics, hidden targets or unavailable billing totals enter features. Missing net is imputed using training-only medians for hidden-model inference; reconstructed true MW still remains missing. Numeric tree features need no scaling. Chronological splits use unique timestamps shared across feeders: first 60% training, next 20% calibration, last 20% held-out test. One fixed CPU configuration (100 depth-4 trees, histogram method, two threads) avoids test tuning. A distinct hyperparameter-validation search is not performed.

Raw XGBoost hidden predictions are clipped to [0, installed capacity] and zeroed outside assumed daylight. Native XGBoost Tree SHAP contributions explain **raw** hidden MW: expected value + contributions = raw prediction. Physical correction is separately reported. SHAP package TreeExplainer is cross-checked against native contributions. Mean absolute contributions provide global summaries; they are explanations of this model and feature distribution, not causal validation.

Calibration uses absolute hidden prediction error on the separate calibration partition and the finite-sample 90% split-conformal quantile. Clipped hidden intervals become true-demand intervals by adding N. Time-series exchangeability is not established, so even synthetic coverage is reported empirically, and no CEB coverage guarantee is claimed. Net-meter errors, unmodelled generation and mapping errors are excluded.

## Evaluation

Apparent demand, direct solar addition, a training-only feeder/clock historical mean of synthetic true demand, and proposed XGBoost are evaluated against simulated independent latent consumption. MAE/RMSE are MW; R² is null for constant reference; MAPE excludes |reference| ≤ 0.001 MW and reports excluded counts. Missing predictions/references are excluded with n reported. Zero-corrupted measured observations remain in observed methods; the synthetic latent reference remains unchanged.

Daily peak magnitude recovery is 100 × predicted daily maximum / reference daily maximum. Peak timing is absolute minutes between each daily argmax (first occurrence for ties), evaluated per feeder and averaged across feeders. This distinguishes magnitude recovery from timing. Scenario metrics include clouds, midday hidden peaks and penetration regimes. A model advantage is never assumed; actual results include the strong historical baseline's access to simulator consumption structure.

CEB evidence reports only balance, sensitivity, night checks and energy reconciliation. Energy uses left-held interval power × duration and excludes missing observations, irregular gaps over 1.5× nominal interval and each feeder's final unbounded interval. Internal balance is not independent validation. Night agreement is conditional on absence of other generation/storage and follows the imposed zero PV envelope. Expert usefulness and stability scores await actual review using the supplied CSV template.

Implementation references: [XGBoost Python API and pred_contribs](https://xgboost.readthedocs.io/en/stable/python/python_api.html), [SHAP TreeExplainer](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html). Supported UBJ serialization stores the model; JSON stores feature/preprocessing/provenance information.
