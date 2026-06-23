"""
Data collection engine — one poll cycle per call.

Reads all configured tags from OPC UA, detects value changes,
and writes changed values to MongoDB. Designed to be called from
st.fragment on a timer so it is always sync-safe.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def collect_once(
    opcua_client,
    mongo_handler,
    tags: List[Dict],
    previous_values: Dict[str, Any],
    threshold: float = 0.01,
    store_on_change: bool = True,
) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Single poll cycle.

    Returns
    -------
    readings : list of dicts with keys path/name/value/unit/timestamp
    updated_prev : new previous_values dict to pass next call
    """
    if not tags or not opcua_client.connected:
        return [], dict(previous_values)

    tag_paths = [t["path"] for t in tags]
    raw = opcua_client.read_tags(tag_paths)
    timestamp = datetime.now(tz=timezone.utc)

    readings: List[Dict] = []
    updated_prev = dict(previous_values)

    for tag in tags:
        path = tag["path"]
        raw_value = raw.get(path)

        if raw_value is None:
            continue

        # Coerce to float where possible
        try:
            value: Any = float(raw_value)
        except (TypeError, ValueError):
            value = raw_value

        reading = {
            "path": path,
            "name": tag.get("name", path),
            "value": value,
            "unit": tag.get("unit", ""),
            "min_range": tag.get("min_range", 0),
            "max_range": tag.get("max_range", 100),
            "timestamp": timestamp,
        }
        readings.append(reading)

        # ------- decide whether to persist -------
        prev = previous_values.get(path)
        should_store = not store_on_change  # always store when change-only is off

        if store_on_change:
            if prev is None:
                should_store = True  # first reading always stored
            elif isinstance(value, (int, float)) and isinstance(prev, (int, float)):
                should_store = abs(float(value) - float(prev)) >= threshold
            else:
                should_store = value != prev

        if should_store:
            updated_prev[path] = value
            if mongo_handler.connected:
                mongo_handler.insert(
                    tag_path=path,
                    tag_name=tag.get("name", path),
                    value=value,
                    unit=tag.get("unit", ""),
                )

    return readings, updated_prev


def append_to_buffer(
    buffer: Dict[str, List[Dict]],
    readings: List[Dict],
    max_points: int = 300,
) -> Dict[str, List[Dict]]:
    """
    Append latest readings to the per-tag rolling buffer.
    Keeps at most max_points entries per tag.
    """
    for r in readings:
        path = r["path"]
        if path not in buffer:
            buffer[path] = []
        buffer[path].append({"timestamp": r["timestamp"], "value": r["value"]})
        if len(buffer[path]) > max_points:
            buffer[path] = buffer[path][-max_points:]
    return buffer
