"""
BESS Decision Support & Headroom Calculation Engine (Stage 3)
Location: src/bess_rules.py
"""
import numpy as np
import pandas as pd

class BESSSimulator:
    def __init__(self, capacity_mwh=2.0, max_power_mw=1.0, soc_min=0.1, soc_max=0.9, initial_soc_mwh=1.0):
        self.capacity_mwh = capacity_mwh
        self.max_power_mw = max_power_mw
        self.soc_min_mwh = capacity_mwh * soc_min
        self.soc_max_mwh = capacity_mwh * soc_max
        self.soc_mwh = initial_soc_mwh
        self.efficiency = 0.95  # Round-trip efficiency factor

    def calculate_headroom(self, ramp_down_prob: float, ramp_up_prob: float):
        """
        Calculates discharge and charge headroom scores (0 to 1) based on SoC and ramp risk.
        """
        # Available energy margins
        energy_above_floor = max(0.0, self.soc_mwh - self.soc_min_mwh)
        energy_below_ceiling = max(0.0, self.soc_max_mwh - self.soc_mwh)

        # Power limitations (MW)
        discharge_power_limit = min(self.max_power_mw, energy_above_floor * 4) # 15-min rate factor (4)
        charge_power_limit = min(self.max_power_mw, energy_below_ceiling * 4)

        # Normalized scores (0 to 1)
        discharge_score = discharge_power_limit / self.max_power_mw
        charge_score = charge_power_limit / self.max_power_mw

        # Rule adjustments based on ramp probabilities
        if ramp_down_prob > 0.5 and self.soc_mwh < self.soc_min_mwh + 0.2:
            # High ramp-down risk but low SoC -> penalty score
            discharge_score *= 0.5

        if ramp_up_prob > 0.5 and self.soc_mwh > self.soc_max_mwh - 0.2:
            # High ramp-up risk but high SoC -> penalty score
            charge_score *= 0.5

        return {
            "discharge_headroom_mw": round(discharge_power_limit, 3),
            "discharge_score": round(discharge_score, 3),
            "charge_headroom_mw": round(charge_power_limit, 3),
            "charge_score": round(charge_score, 3),
            "soc_mwh": round(self.soc_mwh, 3),
            "soc_pct": round((self.soc_mwh / self.capacity_mwh) * 100, 1)
        }

    def step_simulation(self, net_load_delta_mw: float, ramp_down_prob: float, ramp_up_prob: float):
        """
        Simulates one 15-minute operational step based on ramp risk and net load.
        """
        headroom = self.calculate_headroom(ramp_down_prob, ramp_up_prob)

        # Control action rules
        action = "HOLD"
        power_delta_mw = 0.0

        if ramp_down_prob > 0.6 and headroom["discharge_score"] > 0.3:
            # Discharge to absorb ramp-down drop
            action = "DISCHARGE"
            power_delta_mw = min(net_load_delta_mw, headroom["discharge_headroom_mw"])
            energy_change = (power_delta_mw / 4) / self.efficiency
            self.soc_mwh = max(self.soc_min_mwh, self.soc_mwh - energy_change)

        elif ramp_up_prob > 0.6 and headroom["charge_score"] > 0.3:
            # Charge to absorb ramp-up surge
            action = "CHARGE"
            power_delta_mw = min(abs(net_load_delta_mw), headroom["charge_headroom_mw"])
            energy_change = (power_delta_mw / 4) * self.efficiency
            self.soc_mwh = min(self.soc_max_mwh, self.soc_mwh + energy_change)

        return {
            "action": action,
            "power_mw": round(power_delta_mw, 3),
            **headroom
        }

if __name__ == "__main__":
    bess = BESSSimulator()
    print("Initial BESS State:", bess.calculate_headroom(0.2, 0.1))

    # Simulate a high ramp-down event
    step_result = bess.step_simulation(net_load_delta_mw=0.6, ramp_down_prob=0.75, ramp_up_prob=0.05)
    print("Simulation Step Result:", step_result)