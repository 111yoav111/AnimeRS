import config
from services import trace_moe


def _need_second_opinion(similarity: int) -> bool:
    """
    Return True when trace.moe similarity is below the confidence threshold.
    """
    return similarity < config.CONFIDENT_THRESHOLD


def identify(image_bytes: bytes) -> dict:
    """
    Identify an image via trace.moe.

    Returns a dict with 'found' (bool) and 'best_option' (dict | None).

    'confident' is True when similarity >= CONFIDENT_THRESHOLD.
    """
    matches = trace_moe.search(image_bytes)

    if not matches:
        return {
            "found": False,
            "best_option": None,
            "confident": False,
        }

    best_option = max(matches, key=lambda m: m["similarity%"])

    return {
        "found": True,
        "best_option": best_option,
        "confident": not _need_second_opinion(best_option["similarity%"]),
    }
