"""Whitelisted, auditable edits to a parametric yacht hull.

Natural-language interpretation belongs to the calling language model. This
module accepts only explicit structured operations and never executes code.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .hull import HullStation, YachtHull


_ALLOWED_STATION_FIELDS = {
    "x_m", "half_beam_m", "keel_z_m", "chine_z_m", "deck_z_m"
}


def apply_hull_changes(
    hull: YachtHull, changes: list[dict[str, Any]]
) -> tuple[YachtHull, dict[str, Any]]:
    if not isinstance(hull, YachtHull):
        raise TypeError("hull must be a YachtHull")
    if not isinstance(changes, list) or not changes:
        raise ValueError("changes must be a non-empty list")
    before = hull.to_parameters()
    stations = [asdict(s) for s in hull.stations]
    name = hull.name
    fraction = hull.chine_fraction

    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            raise TypeError(f"changes[{index}] must be an object")
        operation = change.get("operation")
        if operation == "set_station":
            station_index = change.get("station_index")
            field = change.get("field")
            value = change.get("value")
            if isinstance(station_index, bool) or not isinstance(station_index, int):
                raise TypeError("station_index must be an integer")
            if not 0 <= station_index < len(stations):
                raise IndexError("station_index is outside the hull station range")
            if field not in _ALLOWED_STATION_FIELDS:
                raise ValueError(f"Unsupported hull station field: {field}")
            stations[station_index][field] = value
        elif operation == "scale_beam":
            factor = change.get("factor")
            if isinstance(factor, bool) or not isinstance(factor, (int, float)):
                raise TypeError("scale_beam factor must be numeric")
            for station in stations:
                station["half_beam_m"] *= factor
        elif operation == "translate_vertical":
            delta = change.get("delta_m")
            if isinstance(delta, bool) or not isinstance(delta, (int, float)):
                raise TypeError("translate_vertical delta_m must be numeric")
            for station in stations:
                for field in ("keel_z_m", "chine_z_m", "deck_z_m"):
                    station[field] += delta
        elif operation == "rename":
            name = change.get("name")
        else:
            raise ValueError(f"Unsupported hull change operation: {operation}")

    updated = YachtHull(
        name=name,
        stations=tuple(HullStation(**item) for item in stations),
        chine_fraction=fraction,
    )
    after = updated.to_parameters()
    diff = {
        "changed": before != after,
        "before": before,
        "after": after,
        "operations": changes,
    }
    return updated, diff
