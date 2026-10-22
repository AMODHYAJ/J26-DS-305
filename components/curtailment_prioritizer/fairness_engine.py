
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
    Calculate provisional historical curtailment burden for five plants.

    Event fields:
        ac_number: plant account number
        timestamp: datetime object or ISO-8601 string
        curtailed_mwh: measured/estimated curtailed energy,
                       or None if unknown

    Lower burden means higher priority for future curtailment,
    but only when historical data coverage is adequate.

    This function does not decide whether curtailment is needed
    or calculate the amount of curtailment.

    IMPORTANT:
        - Weights are provisional.
        - Missing energy is not treated as zero energy.
        - No recorded events do not prove that no curtailment occurred.
        - A definitive priority order is withheld if any plant has
          no recorded dated events.
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

    plants_with_events: set[str] = set()
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

        # Align naive and timezone-aware datetimes.
        if timestamp.tzinfo is not None and as_of.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=None)
        elif timestamp.tzinfo is None and as_of.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=as_of.tzinfo)

        # Ignore future events.
        if timestamp > as_of:
            continue

        item = stats[ac]
        item["event_count"] += 1
        plants_with_events.add(ac)

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

    # Energy is used only when every plant has known energy history.
    energy_available = all(
        item["energy_known"] for item in stats.values()
    )

    if energy_available:
        energy_values = normalise({
            ac: item["energy_mwh"]
            for ac, item in stats.items()
        })
    else:
        energy_values = {ac: 0.0 for ac in stats}

    # Recent-event burden decays linearly over recent_days.
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

    # Disable the energy indicator if energy history is incomplete.
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
                "Normalised historical energy burden: "
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
            reasons.append(
                "No dated curtailment events found; "
                "historical coverage is unverified."
            )

        has_events = ac in plants_with_events

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
            "history_coverage": (
                "recorded_events_found"
                if has_events
                else "no_events_recorded_history_unverified"
            ),
            "reasons": reasons,
        })

    # Lower burden comes first. Account number makes ties deterministic.
    results.sort(
        key=lambda row: (
            row["burden_score"],
            row["ac_number"],
        )
    )

    # Do not present a priority order if any plant has no recorded events.
    history_complete = all(
        ac in plants_with_events for ac in PLANTS
    )

    if not history_complete:
        for row in results:
            row["priority_rank"] = None
            row["ranking_status"] = (
                "provisional_incomplete_history"
            )

        return results

    # Even when every plant has events, the weights and completeness
    # of the historical period still require validation and approval.
    for rank, row in enumerate(results, start=1):
        row["priority_rank"] = rank
        row["ranking_status"] = "provisional"

    return results
