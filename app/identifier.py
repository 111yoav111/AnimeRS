import config
from services import trace_moe


def need_second_opinion(similarity : int) -> bool:
    """
    Return True when trace.moe isnt confident enough; call a other API to check as well.
    """
    return similarity < config.CONFIDENT_THRESHOLD


def identify(image_bytes : bytes) -> dict:
    """
    Identify the image via search() using trace.moe API 
    TODO: Add more API engines 
    """

    matches = trace_moe.search(image_bytes)

    if not matches:
        return {
            "found" : False,
            "best_option" : None,
            "needs_second_opinion" : True
        }
    
    best_option = max(matches, key=lambda m: m["similarity%"])
    
    return {
        "found" : True,
        "best_option" : best_option,
        "needs_second_opinion" : need_second_opinion(best_option["similarity%"])
    }