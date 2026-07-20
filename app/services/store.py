import json
from pathlib import Path
from threading import Lock
from typing import Any

DATA_FILE = Path("/tmp/paul_ai_trader_simulations.json")
_LOCK = Lock()

def _read() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

def list_simulations() -> list[dict[str, Any]]:
    with _LOCK:
        return _read()

def add_simulation(item: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        items = _read()
        items.insert(0, item)
        DATA_FILE.write_text(json.dumps(items[:100], ensure_ascii=False, indent=2), encoding="utf-8")
    return item
