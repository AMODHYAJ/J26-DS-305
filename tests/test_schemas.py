"""
Smoke tests: confirm the synthetic data generators produce objects that
satisfy the frozen contracts, and that the pipeline runs end-to-end.
Run with: python -m pytest tests/  (or python -m tests.test_schemas)
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.demand_analyzer.model import decompose
from components.gis_risk_mapper.model import assess_risk
from components.solar_forecaster.model import forecast
from components.storage_matchmaker.model import recommend
from data.synthetic.billing import synthetic_meter_readings
from data.synthetic.grid_topology import load_test_feeder_ratings
from data.synthetic.spatial import synthetic_plants
from data.synthetic.weather import synthetic_clear_sky_day
from decision_engine.engine import reconcile


def test_end_to_end_pipeline_runs():
    today = datetime(2026, 8, 24)
    weather = synthetic_clear_sky_day(today)
    plants = synthetic_plants()
    ratings = load_test_feeder_ratings()
    feeder_id = ratings[0].feeder_id

    meter_readings = synthetic_meter_readings(feeder_id, "METER-TEST-01", today)

    solar = forecast(feeder_id, weather, plants)
    assert len(solar) == 24
    assert all(0 <= f.p50_kw for f in solar)

    demand = decompose(feeder_id, meter_readings)
    assert len(demand) == 24

    sub = next(r for r in ratings if r.feeder_id == feeder_id)
    risks = assess_risk(sub, solar, demand)
    assert len(risks) == 24

    advice = reconcile(sub, solar, risks)
    assert len(advice) == len(risks)

    rec = recommend(sub.substation_id, avg_ramp_rate_kw_per_min=25.0)
    assert rec.lcos_usd_per_mwh > 0


if __name__ == "__main__":
    test_end_to_end_pipeline_runs()
    print("OK — synthetic pipeline runs end-to-end.")
