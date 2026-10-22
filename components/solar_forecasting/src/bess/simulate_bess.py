"""
Stage 3: BESS (Battery Energy Storage System) Decision Support Simulation.
Location: src/bess/simulate_bess.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" / "embilipitiya_ramps_classified_15min.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "bess_simulation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_bess_simulation():
    print("=======================================================")
    print("Stage 3: BESS Decision Support Simulation")
    print("=======================================================")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Classified dataset not found at {DATA_PATH}. Run detect_ramps.py first.")

    df = pd.read_csv(DATA_PATH)
    df['datetime'] = pd.to_datetime(df['datetime_utc'])
    df = df.sort_values(['plant_id', 'datetime']).reset_index(drop=True)

    # BESS Parameters (Scaled from Anuradhapura/Galle reference systems)
    max_power_kw = 1000.0  # 1 MW max charge/discharge power
    max_energy_kwh = 2000.0 # 2 MWh total capacity
    soc_min = 0.10 * max_energy_kwh # 10% floor
    soc_max = 0.90 * max_energy_kwh # 90% ceiling
    initial_soc = 0.50 * max_energy_kwh # 50% initial state of charge
    efficiency = 0.95 # Round-trip efficiency factor

    results = []

    print("Running 15-minute BESS dispatch replay across plant clusters...")
    for plant_id, group in df.groupby('plant_id'):
        group = group.sort_values('datetime').copy()
        soc = initial_soc

        soc_history = []
        headroom_discharge = []
        headroom_charge = []

        for idx, row in group.iterrows():
            gen = row.get('generation_kw', 0.0)
            if pd.isna(gen):
                gen = 0.0
            ramp = row.get('ramp_class', 'Stable')
            delta_p = row.get('delta_p_kw', 0.0)
            if pd.isna(delta_p):
                delta_p = 0.0

            # Rule-based dispatch logic
            if ramp == 'Ramp-Down' and abs(delta_p) > 0:
                required_power = abs(delta_p) * 1000
                discharge_power = min(required_power, max_power_kw)
                energy_needed = (discharge_power * 0.25) # 15-min interval

                if (soc - energy_needed) >= soc_min:
                    soc -= energy_needed
            elif ramp == 'Ramp-Up' and abs(delta_p) > 0:
                surplus_power = abs(delta_p) * 1000
                charge_power = min(surplus_power, max_power_kw)
                energy_stored = (charge_power * 0.25) * efficiency

                if (soc + energy_stored) <= soc_max:
                    soc += energy_stored

            # Compute operational headroom scores (0 to 1)
            usable_energy = soc - soc_min
            discharge_headroom_score = min(max(usable_energy / (max_energy_kwh * 0.8), 0.0), 1.0)

            usable_space = soc_max - soc
            charge_headroom_score = min(max(usable_space / (max_energy_kwh * 0.8), 0.0), 1.0)

            soc_history.append(soc)
            headroom_discharge.append(discharge_headroom_score)
            headroom_charge.append(charge_headroom_score)

        group['bess_soc_kwh'] = soc_history
        group['discharge_headroom_score'] = headroom_discharge
        group['charge_headroom_score'] = headroom_charge
        results.append(group)

    df_simulated = pd.concat(results, ignore_index=True)
    output_path = OUTPUT_DIR / "bess_simulation_results_15min.csv"
    df_simulated.to_csv(output_path, index=False)

    print(f"\n[Success] BESS simulation completed and saved to {output_path}")
    print(f"Total simulated intervals: {len(df_simulated):,}")


if __name__ == "__main__":
    run_bess_simulation()