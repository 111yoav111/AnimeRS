import httpx 

import config


def get_quota() -> dict:
    """
    Fetch current quota status from trace.moe /me endpoint.
 
    Returns a dict with:
        quota - total daily searches allowed
        quota_used - searches used in the last 24 hours (rolling window)
        quota_left - quota - quota_used
        low_quota - True if remaining <= QUOTA_LOW_THRESHOLD
    """
    resp = httpx.get(
        f"{config.TRACE_MOE_BASE_URL}/me",
        timeout=config.TRACE_MOE_TIMER,
    )
    resp.raise_for_status()
    data = resp.json()

    quota = data.get("quota")
    quota_used = data.get("quotaUsed")

    if quota is None or quota_used is None:
        raise RuntimeError(f"Error with /me response: {data}")
    quota_used = int(quota_used)
    
    quota_left = quota - quota_used

    return {
        "quota": quota,
        "quota_used": quota_used,
        "remaining": quota_left,
        "low_quota": quota_left <= config.QUOTA_LOW_THRESHOLD,
    }
