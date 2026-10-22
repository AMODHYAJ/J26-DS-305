# Supplied CEB evidence

All 11 files were opened or scanned; source files are unchanged and outside Git. Full machine-readable, column-level audit is generated in ignored `C2_TLA_outputs/C2_TLA_data_audit.json`. It records file SHA-256, every worksheet/table/column, duplicate and missing counts, numeric ranges, zeros and negative values. The Access audit scans every table in read-only mode; private samples stay local. No customer/account records are committed.

| Evidence | Observed structure | Interpretation |
|---|---|---|
| `GSPL_Output_20261020_200410.xlsx` | Summary plus GSS/device sheets; 92 daily rows/channel; 96 quarter-hour fields/day, 2026-07-01 through 2026-09-30 | Measured operational MW or AMP as identified by each row's Analog field. Summary values are daily statistics, not extra measurements. |
| `EMB-EMB.xlsx` | Embedded-generation report, 941 rows × 23 columns | Paginated transformer/scheme summary and account/capacity/agreement-date detail; no consumption or interval generation. |
| `EMB-GOD.xlsx` | 490 × 23 | Same report format; preserve GSS, CSC, feeder, section, SIN and scheme. |
| `EMB-KOL.xlsx` | 262 × 23 | Same report format. |
| `EMB-UDA.xlsx` | 559 × 23 | Same report format. |
| `Rathnapura Area Malwala CSC SIN wise installed solar capacity.xlsx` | 164 × 23 | Capacity register for another area; not silently joined to Embilipitiya telemetry. |
| `Loads.xlsx` | 2,156 records, 28 columns | SectionId, three-phase kW/kvar/kVA and kWh plus allocation flags. Static network model; all phase kWh values zero. |
| `Gnodes.xlsx` | 24,925 records, seven columns | SectionId, sequence, X/Y, longitude/latitude and schematic flag; geometry, not demand. |
| `Vishmi/solar_with_coords.csv` | 357 rows, 21 columns | Derived transformer-capacity/location table: 62 coordinate matches, 295 missing. Retained as contextual derivative, not additional capacity to sum with registers. |
| Base-model `.mdb` | 99 user tables, including empty tables | Network model, equipment defaults, seasonal profiles and scenarios, not a billing database. See generated schema inventory. |
| Curtailment JPEG | Visual table dated 2026-10-19, capacity MW and status at 08:20 | Includes hydro, solar, dendro and wind; no interval output. Image visually inspected. Not converted into PV observations. |

## Measurement and mapping findings

Ten Embilipitiya feeder MW channels contain 88,320 quarter-hour records. Seven have capacity-register matches, leaving 61,824 reconstructed intervals. F3, F9 and F10 are excluded from reconstruction because absent capacity coverage is not equivalent to zero capacity.

Across those ten measured channels: no missing cells, 28,498 exact zeros and 9,361 negative values. Distinct feeder/timestamp keys are enforced; repeated numeric readings are not mistaken for duplicate records. All five capacity reports reconcile summary/detail totals at **29,650.47 kW** across **1,453 account-detail rows** and **390 composite transformer groups**, without adding summary and detail together. The parser handles the CSC label moving between columns in the report's summary/detail sections. This total spans several GSS regions and is not all Embilipitiya capacity. The audit covers **91 worksheets**, including the GSPL workbook's 84 sheets.

| Register feeder | Measurement device | Network-model feeder | Registered MW | Net MW range |
|---|---|---|---:|---:|
| Feeder 01 | 3_EMBIL_F1 | EMBILIPITIYA_F1 | 0.18055 | −4.359 to 12.560 |
| Feeder 02 | 3_EMBIL_F2 | EMBILIPITIYA_F2 | 2.66668 | −1.390 to 4.352 |
| Feeder 04 | 3_EMBIL_F4 | EMBILIPITIYA_F4 | 2.58992 | −8.703 to 9.086 |
| Feeder 05 | 3_EMBIL_F5 | EMBILIPITIYA_F5 | 2.33492 | −1.375 to 8.015 |
| Feeder 06 | 3_EMBIL_F6 | EMBILIPITIYA_F6 | 5.95059 | −0.002958 to 0.002749 |
| Feeder 07 | 3_EMBIL_F7 | EMBILIPITIYA_F7 | 5.92814 | −0.003816 to 0.003723 |
| Feeder 08 | 3_EMBIL_F8 | EMBILIPITIYA_F8 | 1.80339 | −0.004367 to 0.004344 |

These are **provisional ordinal crosswalks**, supported by explicit GSS/feeder labels, `InstFeeders.FeederId` values and `InstMeterPoints.Description` (including EMBILIPITIYA_F1). There is no source-issued telemetry-to-register crosswalk. No fuzzy matching is used. The network SectionId of a meter is a separate key; it is not assumed equal to measurement device ID. SIN identifiers alone can repeat across sections/CSCs; retain composite context.

The F6–F8 magnitudes are suspicious near-zero channels, not proof of unloaded feeders. F1/F4 export can exceed registered PV capacity: possible incomplete generation coverage, wrong mapping, sign/scaling problems, or non-solar generation. Real readings are retained with warnings. Demand below zero after PV reconstruction is an inconsistency flag, not clipped away. No observations are silently removed as statistical outliers. Naive timestamps are localized to Asia/Colombo as an explicit study-area assumption, not a property embedded in the file.

## Access investigation and billing semantics

Read with `Microsoft.ACE.OLEDB.12.0`, mode Read, after discovering ODBC only offered SQL Server. Important counts: `InstFeeders` 61, `InstSection` 6,775, `Gnodes` 24,925, `Node` 6,630, `Loads` 2,156, `InstMeterPoints` 87, `InstMeterDmd` 4,176, `DevCustLoadCurves` 480, `InstGenerators` 87, `InstDGens` 4. `InstCustomers` and `InstMymCustomers` are empty. Scenario tables (`InstMymLoads`: 22,576, `InstMymGenerators`: 957) are model variants, not extra observations.

`Loads.Phase1Kwh/Phase2Kwh/Phase3Kwh` are zero in every row. `InstMeterDmd` has Season/DayType and hourly percentage load/demand columns fixed at 100, not dated demand traces. `InstMeterPoints` contains static values and historical meter dates (including 1899 defaults and 2018/2023), not 2026 interval measurements. Seasonal/hourly equipment profiles do not become measured gross consumption merely because their names contain demand or meter.

Account fields in the spreadsheets identify connections, capacity and agreement dates. Net Metering, Net Accounting, Net Plus and Net Plus Plus describe schemes; they do not reveal contemporaneous gross load or self-consumption. No defensible monthly billed usage or independent true-demand target was found. Installed capacity is not actual generation. No monthly kWh is treated as MW. The optional billing adapter requires period, unit, meter meaning and availability metadata and deliberately excludes unverified billing totals from model features.

Future CEB inputs required for independent validation: approved feeder boundary/crosswalk and telemetry scaling, time-effective capacity/commissioning records, measured feeder PV/other generation and storage, meter import/export intervals, documented billing semantics and independent gross consumption where feasible. These do not prevent the implemented measured-net reconstruction workflow.
