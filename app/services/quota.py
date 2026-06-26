import httpx 

import config


def get_quota() -> dict:
    """
    Fetch current quota status from trace.moe /me endpoint.
 
    Returns a dict with:
        quota - total daily searches allowed
        quota_used - searches used in the last 24 hours (rolling window)
        quota_left - quota - quota_used
        low_quota - True if remaining <= QUOTA_LOW_THRESHOL
    """
    headers = {}
    # If having an API key - have more searches 
    if config.TRACE_MOE_API_KEY:
        headers["x-trace-key"] = config.TRACE_MOE_API_KEY

    resp = httpx.get(
        f"{config.TRACE_MOE_BASE_URL}/me",
        headers=headers,
        timeout=config.TRACE_MOE_TIMER,
    )
    resp.raise_for_status()
    data = resp.json()
    print(data)

    quota = data.get("quota")
    quota_used = int(data.get("quotaUsed"))

    if quota is None or quota_used is None:
        raise RuntimeError(f"Error with /me response: {data}")
    
    quota_left = quota - quota_used

    return {
        "quota": quota,
        "quota_used": quota_used,
        "remaining": quota_left,
        "low_quota": quota_left <= config.QUOTA_LOW_THRESHOLD,
    }
