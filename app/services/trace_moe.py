import re

import httpx
import config

# Common ways sequel seasons show up in an English/Romaji title on AniList,
# e.g. "Attack on Titan Final Season", "Kaguya-sama 3rd Season", "Frieren Season 2".
# Checked in order - first match wins.
_SEASON_PATTERNS = [
    re.compile(r"(\d+)(?:st|nd|rd|th)\s+Season", re.IGNORECASE),
    re.compile(r"Season\s+(\d+)", re.IGNORECASE),
    re.compile(r"Season\s+([IVXLCDM]+)\b"),
]

_ROMAN_NUMERALS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}


def _extract_season_number(*titles: str | None) -> int | None:
    """
    Pull season number out of a title string.

    trace.moe/AniList don't expose season number as a clean field - each season is its own separate anime entry.
    so this only works when the title itself spells it out. 
    
    Returns None if nothing matches.
    """
    for title in titles:
        if not title:
            continue
        for pattern in _SEASON_PATTERNS:
            match = pattern.search(title)
            if not match:
                continue
            token = match.group(1)
            if token.isdigit():
                return int(token)
            if token.upper() in _ROMAN_NUMERALS:
                return _ROMAN_NUMERALS[token.upper()]
    return None


def search(image_bytes: bytes) -> list[dict]:
    """
    API-POST image_bytes -> trace.moe/search.

    Returns a list of cleaned (only important stuff) result dicts, best matches show first.

    Raises RuntimeError on API-level errors, httpx.HTTPStatusError on HTTP errors.
    """
    params = {"anilistInfo": ""}
    if config.TRACE_MOE_CUT_BORDERS:
        params["cutBorders"] = ""

    headers = {}
    if config.TRACE_MOE_API_KEY:
        headers["x-trace-key"] = config.TRACE_MOE_API_KEY

    files = {"image": image_bytes}

    resp = httpx.post(
        f"{config.TRACE_MOE_BASE_URL}/search",
        params=params,
        files=files,
        headers=headers,
        timeout=config.TRACE_MOE_TIMER,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(f"trace.moe error: {data['error']}")

    return [_clean_resp(res) for res in data.get("result", [])]


def _fmt_timestamp(seconds: float | None) -> str:
    """
    Convert a raw seconds float to a mm:ss string.
    """
    if seconds is None:
        return "00:00"
    total = int(seconds)
    mm = total // 60
    ss = total % 60
    return f"{mm:02d}:{ss:02d}"


def _clean_resp(anw: dict) -> dict:
    """
    Clean up API result, so it include only the important parts.

    similarity% is an int 0–100 to match CONFIDENT_THRESHOLD in config.
    """
    anime_list = anw.get("anilist") or {}
    title = anime_list.get("title") or {}

    english_title = title.get("english") or None
    romaji_title = title.get("romaji") or None

    season_number = _extract_season_number(english_title, romaji_title)

    return {
        "English Title": english_title,
        "Romaji": romaji_title,
        "Native Title": title.get("native")  or None,
        "Episode": anw.get("episode") or None,
        "Timestamp": _fmt_timestamp(anw.get("from")),
        "Season": f"Season {season_number}" if season_number else None,
        "similarity%": int((anw.get("similarity") or 0) * 100),
        "animelist_id": anime_list.get("id") or "Unknown",
    }
