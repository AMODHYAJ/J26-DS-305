
import unittest
from datetime import datetime

from fairness_engine import PLANTS, rank_plants


class TestFairnessEngine(unittest.TestCase):

    def test_all_five_plants_are_returned(self):
        results = rank_plants([])
        self.assertEqual(len(results), 5)
        self.assertEqual(
            {row["ac_number"] for row in results},
            set(PLANTS.keys()),
        )



    def test_lower_historical_burden_gets_higher_priority(self):
        events = [
            {
                "ac_number": "6470900542",
                "timestamp": "2026-09-01T10:00:00",
                "curtailed_mwh": 10,
            },
            {
                "ac_number": "6470900534",
                "timestamp": "2026-09-01T10:00:00",
                "curtailed_mwh": 2,
            },
        ]

        # Give every plant a known energy value so the energy
        # indicator is available for the complete five-plant set.
        events.extend([
            {
                "ac_number": "6470900607",
                "timestamp": "2026-09-01T10:00:00",
                "curtailed_mwh": 0,
            },
            {
                "ac_number": "6470900828",
                "timestamp": "2026-09-01T10:00:00",
                "curtailed_mwh": 0,
            },
            {
                "ac_number": "6470900836",
                "timestamp": "2026-09-01T10:00:00",
                "curtailed_mwh": 0,
            },
        ])

        results = rank_plants(
            events,
            as_of=datetime(2026, 10, 21),
            weights={
                "energy": 1.0,
                "recent": 0.0,
                "frequency": 0.0,
            },
        )

        by_ac = {row["ac_number"]: row for row in results}

        self.assertLess(
            by_ac["6470900534"]["burden_score"],
            by_ac["6470900542"]["burden_score"],
        )
        self.assertLess(
            by_ac["6470900534"]["priority_rank"],
            by_ac["6470900542"]["priority_rank"],
        )



    def test_unknown_plants_are_ignored(self):
        results = rank_plants([
            {
                "ac_number": "UNKNOWN",
                "timestamp": "2026-10-10T10:00:00",
                "curtailed_mwh": 5,
            }
        ])
        self.assertEqual(len(results), 5)

    def test_negative_energy_is_rejected(self):
        with self.assertRaises(ValueError):
            rank_plants([{
                "ac_number": "6470900542",
                "timestamp": "2026-10-10T10:00:00",
                "curtailed_mwh": -1,
            }])


if __name__ == "__main__":
    unittest.main(verbosity=2)
