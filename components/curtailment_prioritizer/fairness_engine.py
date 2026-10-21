
from datetime import datetime, timedelta
from typing import Any


PLANTS = {
    "6470900542": {
        "name": "Laugfs Solar",
        "capacity_mw": 1.0,
    },
    "6470900534": {
        "name": "Irish & Eco Solar",
        "capacity_mw": 1.0,
    },
    "6470900607": {
        "name": "Dimo Solar / Thunkama",
        "capacity_mw": 1.0,
    },
    "6470900828": {
        "name": "Chandrikawewa Floating Solar",
        "capacity_mw": 1.0,
    },
    "6470900836": {
        "name": "Kiriibbanwewa Floating Solar",
        "capacity_mw": 1.0,
    },
}

DEFAULT_WEIGHTS = {
    "energy": 0.50,
    "recent": 0.30,
    "frequency": 0.20,
}


def rank_plants(
        events: list[dict[str, Any]],
        as_of: datetime | None = None,
        recent_days: int = 30,
        weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    Rank the five identified solar plants by historical
    curtailment burden.

    Event fields:
        ac_number: plant account number
        timestamp: datetime object or ISO-8601 string
        curtailed_mwh: measured/estimated curtailed energy,
                       or None if unknown

    Lower burden means higher priority for future curtailment.

    Important:
        - Weights are provisional, not an approved fairness policy.
        - Missing energy is not treated as confirmed zero energy.
        - This function ranks plants only. It does not decide
          whether curtailment is needed or calculate its amount.
    """
    if recent_days <= 0:
        raise ValueError("recent_days must be greater than zero.")

    as_of = as_of or datetime.now()

    selected_weights = dict(
        DEFAULT_WEIGHTS if weights is None else weights
    )

    expected_keys = {"energy", "recent", "frequency"}

    if set(selected_weights) != expected_keys:
        raise ValueError(
            "Weights must contain energy, recent, and frequency."
        )

    if any(
            not isinstance(value, (int, float))
            or value < 0
            for value in selected_weights.values()
    ):
        raise ValueError("Weights must be non-negative numbers.")

    weight_total = sum(selected_weights.values())

    if weight_total <= 0:
        raise ValueError("At least one weight must be positive.")

    selected_weights = {
        key: value / weight_total
        for key, value in selected_weights.items()
    }

    stats = {
        ac: {
            "energy_mwh": 0.0,
            "energy_known": False,
            "event_count": 0,
            "recent_event_count": 0,
            "last_event": None,
        }
        for ac in PLANTS
    }

    cutoff = as_of - timedelta(days=recent_days)

    for event in events:
        ac = str(event.get("ac_number", "")).strip()

        # Only process the five in-scope plants.
        if ac not in stats:
            continue

        raw_timestamp = event.get("timestamp")

        if not raw_timestamp:
            continue

        try:
            timestamp = (
                raw_timestamp
                if isinstance(raw_timestamp, datetime)
                else datetime.fromisoformat(str(raw_timestamp))
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid timestamp for plant {ac}: "
                f"{raw_timestamp!r}"
            ) from exc

        # Align naive/aware datetimes for comparison.
        if timestamp.tzinfo is not None and as_of.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=None)
        elif timestamp.tzinfo is None and as_of.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=as_of.tzinfo)

        item = stats[ac]

        # Ignore future events rather than counting them as history.
        if timestamp > as_of:
            continue

        item["event_count"] += 1

        if (
                item["last_event"] is None
                or timestamp > item["last_event"]
        ):
            item["last_event"] = timestamp

        raw_energy = event.get("curtailed_mwh")

        if raw_energy not in (None, ""):
            try:
                energy = float(raw_energy)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid curtailed_mwh for plant {ac}."
                ) from exc

            if energy < 0:
                raise ValueError(
                    f"curtailed_mwh cannot be negative for {ac}."
                )

            item["energy_known"] = True
            item["energy_mwh"] += energy

        if timestamp >= cutoff:
            item["recent_event_count"] += 1

    def normalise(
            values: dict[str, float],
    ) -> dict[str, float]:
        maximum = max(values.values(), default=0.0)

        if maximum <= 0:
            return {key: 0.0 for key in values}

        return {
            key: value / maximum
            for key, value in values.items()
        }

    # Score energy only if each plant has known energy history.
    # If history is incomplete, exclude the energy indicator.
    energy_available = all(
        item["energy_known"] for item in stats.values()
    )

    if energy_available:
        energy_values = normalise({
            ac: item["energy_mwh"]
            for ac, item in stats.items()
        })
    else:
        energy_values = {
            ac: 0.0 for ac in stats
        }

    # Higher recency burden means the plant was curtailed recently.
    # The burden decays linearly to zero over recent_days.
    recency_values = {}

    for ac, item in stats.items():
        last_event = item["last_event"]

        if last_event is None:
            recency_values[ac] = 0.0
            continue

        age_days = max(
            0.0,
            (as_of - last_event).total_seconds() / 86400,
            )

        recency_values[ac] = max(
            0.0,
            1.0 - age_days / recent_days,
            )

    frequency_values = normalise({
        ac: item["event_count"]
        for ac, item in stats.items()
    })

    # If energy is unavailable, redistribute its weight across
    # recency and frequency instead of assigning zero burden
    # to every plant.
    active_weights = dict(selected_weights)

    if not energy_available:
        active_weights["energy"] = 0.0


    active_total = sum(active_weights.values())

    if active_total > 0:
        active_weights = {
            key: value / active_total
            for key, value in active_weights.items()
        }
    else:
        # If every configured indicator is unavailable,
        # use recency and frequency as a fallback.
        active_weights = {
            "energy": 0.0,
            "recent": 0.5,
            "frequency": 0.5,
    }


    results = []

    for ac, item in stats.items():
        burden = (
                active_weights["energy"] * energy_values[ac]
                + active_weights["recent"] * recency_values[ac]
                + active_weights["frequency"] * frequency_values[ac]
        )

        reasons = []

        if energy_available:
            reasons.append(
                f"Normalised historical energy burden: "
                f"{energy_values[ac]:.3f}"
            )
        else:
            reasons.append(
                "Energy indicator excluded because complete "
                "energy history is unavailable for all five plants."
            )

        reasons.append(
            f"{item['event_count']} dated curtailment event(s)."
        )

        reasons.append(
            f"{item['recent_event_count']} event(s) in the "
            f"last {recent_days} days."
        )

        if item["last_event"] is not None:
            reasons.append(
                "Most recent recorded event: "
                f"{item['last_event'].isoformat()}."
            )
        else:
            reasons.append("No dated curtailment events found.")

        results.append({
            "ac_number": ac,
            "plant_name": PLANTS[ac]["name"],
            "capacity_mw": PLANTS[ac]["capacity_mw"],
            "historical_energy_mwh": (
                round(item["energy_mwh"], 3)
                if item["energy_known"]
                else None
            ),
            "energy_history_known": item["energy_known"],
            "event_count": item["event_count"],
            "recent_event_count": item["recent_event_count"],
            "last_event": (
                item["last_event"].isoformat()
                if item["last_event"] is not None
                else None
            ),
            "burden_score": round(burden, 4),
            "reasons": reasons,
        })

    # Lower burden = higher priority.
    # Account number provides deterministic tie-breaking.
    results.sort(
        key=lambda row: (
            row["burden_score"],
            row["ac_number"],
        )
    )

    for rank, row in enumerate(results, start=1):
        row["priority_rank"] = rank

    return results
