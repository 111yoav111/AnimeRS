import httpx
import config


def search(image_bytes: bytes) -> list[dict]:
    """
    API-POST image_bytes -> trace.moe/search.

    Returns a list of cleaned (only important stuff) result dicts, best matches show first.

    Raises RuntimeError on API-level errors, httpx.HTTPStatusError on HTTP errors.
    """
    params = {"anilistInfo": ""}
    if config.TRACE_MOE_CUT_BORDERS:
        params["cutBorders"] = ""

    files = {"image": image_bytes}

    resp = httpx.post(
        f"{config.TRACE_MOE_BASE_URL}/search",
        params=params,
        files=files,
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

    return {
        "English Title": title.get("english") or "Unknown",
        "Romaji": title.get("romaji")  or "Unknown",
        "Native Title": title.get("native")  or "Unknown",
        "Episode": anw.get("episode") or None,
        "Timestamp": _fmt_timestamp(anw.get("from")),
        "similarity%": int((anw.get("similarity") or 0) * 100),
        "animelist_id": anime_list.get("id") or "Unknown",
    }