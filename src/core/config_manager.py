import json
from pathlib import Path
from typing import Any, Dict

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "settings.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "opcua": {
        "server_url": "",
        "username": "",
        "password": "",
        "use_auth": False,
        "session_timeout": 3600000,
    },
    "mongodb": {
        "uri": "",
        "database": "",
        "collection": "",
    },
    "openai": {
        "api_key": "",
    },
    "tags": [],
    "monitoring": {
        "poll_interval": 1,
        "store_on_change_only": True,
        "change_threshold": 0.01,
    },
}


def load_config() -> Dict[str, Any]:
    """Load user config, falling back to defaults for any missing keys."""
    if not _CONFIG_PATH.exists():
        _write(DEFAULT_CONFIG)
        return _deep_copy(DEFAULT_CONFIG)

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        stored = json.load(f)

    merged = _deep_copy(DEFAULT_CONFIG)
    _deep_merge(merged, stored)
    return merged


def save_config(config: Dict[str, Any]) -> None:
    """Persist config to disk."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write(config)


def _write(config: Dict[str, Any]) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _deep_copy(d: dict) -> dict:
    return json.loads(json.dumps(d))


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
