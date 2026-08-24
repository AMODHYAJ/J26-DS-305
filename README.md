# S-GISM — Solar-Grid Intelligence & Storage Management (Prototype Scaffold)

Project ID: J26-DS-305 (IT4010 Research Project, CoEAI)

## Why this scaffold exists

The external supervisor (CEB) hasn't delivered feeder A/V data, GPS/capacity
data, or billing/net-metering data yet. Rather than wait, every component in
this repo is built against **synthetic/proxy data that obeys the same schema
the real CEB data will use** (see `schemas/contracts.py`). When the real data
arrives, you write one new loader per stream in `data/real/` (not created
yet) that maps CEB's actual columns onto the frozen schema — nothing in
`components/` or `decision_engine/` has to change.

## Layout

```
s-gism/
├── schemas/contracts.py        # frozen data contracts (Layer 1 + component outputs)
├── data/synthetic/             # proxy data generators — swap these out later
│   ├── weather.py               # NASA POWER API pull for Embilipitiya
│   ├── grid_topology.py         # IEEE 13-bus feeder via OpenDSS (dss-python)
│   ├── spatial.py                # synthetic rooftop/ground-mount GPS points
│   └── billing.py                # synthetic residential/commercial load curves
├── components/
│   ├── solar_forecaster/        # Component 1 — Jayathilaka
│   ├── demand_analyzer/         # Component 2 — Hapuarachchi
│   ├── gis_risk_mapper/         # Component 3 — Edirisinghe
│   └── storage_matchmaker/      # Component 4 — Geethma
├── decision_engine/engine.py    # Layer 3 — reconciles Components 1–4 → dispatch advice
├── dashboard/app.py             # Layer 4 — Streamlit NSO dashboard (Views A/B/C)
└── tests/                        # schema + smoke tests
```

## Getting started

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m tests.test_schemas          # sanity-check the contracts
streamlit run dashboard/app.py        # see the full pipeline end-to-end
```

## Ownership (per the TAF sub-objectives)

| Component | Owner | Folder |
|---|---|---|
| 1 — Solar Forecaster (kW + Ramp Rate) | Jayathilaka | `components/solar_forecaster/` |
| 2 — Demand Analyzer (True Demand vs Net Load) | Hapuarachchi | `components/demand_analyzer/` |
| 3 — GIS Risk Mapper (reverse power flow) | Edirisinghe | `components/gis_risk_mapper/` |
| 4 — Storage Matchmaker (LCOS-based) | Geethma | `components/storage_matchmaker/` |
| Decision Engine + Dashboard | All members | `decision_engine/`, `dashboard/` |

## Swap-in checklist once CEB data arrives

- [ ] Feeder A/V + substation ratings → replace `data/synthetic/grid_topology.py`
      with a real loader; retire the IEEE 13-bus stand-in.
- [ ] GPS/capacity of rooftop + ground-mounted plants → replace
      `data/synthetic/spatial.py`.
- [ ] CEB/LECO billing (Net Metering/Plus) → replace `data/synthetic/billing.py`.
- [ ] Historical ground-mounted plant generation (validation proxy) → retrain
      Component 1 on the real series instead of the public PV dataset stand-in.

Each item is a data-loader swap, not a redesign, as long as the new loader
still returns objects matching `schemas/contracts.py`.
