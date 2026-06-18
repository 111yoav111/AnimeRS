import httpx
import config


def search(image_bytes : bytes) -> list[dict]:
    """
        
    """
    parms = {"anilistInfo": ""}
    if config.TRACE_MOE_CUT_BORDERS:
        parms["cutBorders"] = ""

    files = {"image" : image_bytes}

    resp = httpx.post(
        f"{config.TRACE_MOE_BASE_URL}/search",
        params=parms,
        files=files,
        timeout= config.TRACE_MOE_TIMER
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(f"trace.moe error: {data["error"]}")
        
        #TODO return
    return [_clean_resp(res) for res in data.get("result", [])]

    
def _clean_resp(anw : dict) -> dict:
    """
        
    """
    anime_list = anw.get("anilist") or {}
    title = anime_list.get("title") or {}
    name_english = title.get("english") or "Unknow"
    name_romaji = title.get("romaji")  or "Unknow"
    name_native = title.get("native") or "Unknow"
    time_minute = int(anw.get("from") / 60)

    return {
        "English Title" : name_english,
        "Romaji" : name_romaji,
        "Native Title" : name_native,
        "Episode" : anw.get("episode") or None,
        "From - Minute" : time_minute,
        "similarity%" : int(anw.get("similarity") * 100),
        "animelist_id" : anime_list.get("id", "Unknow")

    }
