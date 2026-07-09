import json
import logging
import os
import sys
import time
from pathlib import Path

import config

logger = logging.getLogger(__name__)


def _data_dir() -> Path:
    """
    Per-user directory for AnimeRS's local data, following each OS's own
    convention. Not the exe/install folder, since packaged builds may run
    from a read-only location (e.g. Program Files, /Applications).
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or Path.home()
        return Path(base) / "AnimeRS"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AnimeRS"
    # Linux and other Unix-likes - XDG Base Directory spec
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "AnimeRS"


HISTORY_PATH = _data_dir() / "history.json"


def load_history() -> list[dict]:
    """
    Return saved search entries, most recent first.
    Empty list if none saved yet or the file is missing/corrupt.
    """
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add_entry(verdict: dict, filename: str) -> None:
    """
    Prepend a search result to history, trimmed to the last
    config.HISTORY_MAX_ENTRIES entries (oldest dropped first).

    Never raises - history is a nice-to-have and shouldn't fail an
    otherwise-successful search.
    """
    try:
        entries = load_history()
        entries.insert(0, {
            "searched_at": time.time(),
            "filename": filename,
            "verdict": verdict,
        })
        entries = entries[:config.HISTORY_MAX_ENTRIES]

        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f)
    except Exception as exc:
        logger.warning("Failed to save search history: %s", exc)
