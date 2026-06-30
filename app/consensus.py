import logging
from collections import defaultdict
import time

import config
from services import trace_moe

logger = logging.getLogger(__name__)


def _fmt_timestamp(seconds: float | None) -> str:
    """
    Convert raw seconds to readable time -> mm:ss.
    """
    if not seconds:
        return "00:00"
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def _vote(results: list[list[dict]]) -> tuple[str, list[dict]] | None:
    """
    Vote across all frame results.
    Each frame casts a vote for its best match via animelist_id, his weight is based on the similarity%.

    Returns the winning animelist_id's best result dict, or None if no results.
    """
    best_match: dict[str, list[dict]] = defaultdict(list)

    for frame_results in results:
        if not frame_results:
            continue
        best = max(frame_results, key=lambda m: m["similarity%"])
        animelist_id = best.get("animelist_id")
        if animelist_id and animelist_id != "Unknown":
            best_match[animelist_id].append(best)

    if not best_match:
        return None

    chosen_id = max(
        best_match,
        key=lambda id: sum(m["similarity%"] for m in best_match[id])
    )
    return chosen_id, best_match[chosen_id]


def calc_timestamp(matches: list[dict], duration_sec: float = 0.0) -> tuple[str | None, str | None]:
    """
    Build timestamp output from winning frame matches.
    - Single frame (image) : exact timestamp "mm:ss"
    - Multiple frames (video/gif): start = first frame timestamp, end = start + video duration
    """
    raw_seconds = []

    for m in matches:
        ts = m.get("Timestamp", "00:00")
        try:
            parts = ts.split(":")
            seconds = int(parts[0]) * 60 + int(parts[1])
            raw_seconds.append(seconds)
        except Exception:
            continue

    if not raw_seconds:
        return None, None

    raw_seconds.sort()

    if len(raw_seconds) == 1 and duration_sec == 0.0:
        # still image - return exact timestamp
        return _fmt_timestamp(raw_seconds[0]), None
    else:
        # video/GIF - start + duration = end
        start = raw_seconds[0]
        end = start + int(duration_sec) if duration_sec and duration_sec != float('inf') else start
        return None, f"{_fmt_timestamp(start)} – {_fmt_timestamp(end)}"


def build_verdict(frames: list[bytes], duration_sec: float = 0.0) -> dict:
    """
    Run all frames through trace.moe -> vote on results -> build final verdict.
    """
    frames_total = len(frames)
    logger.info("Running consensus on %d frames", frames_total)

    all_results: list[list[dict]] = []
    for i, frame in enumerate(frames):
        try:
            results = trace_moe.search(frame)
            all_results.append(results)
            logger.debug("Frame %d - %d matches", i, len(results))
        except Exception as exc:
            logger.warning("Frame %d failed: %s", i, exc)
            all_results.append([])
        if i < len(frames) - 1:  # no need to sleep after last frame
            time.sleep(1)

    vote_result = _vote(all_results)

    if vote_result is None:
        logger.warning("No consensus reached, no matches found")
        return {
            "found": False,
            "anime": None,
            "episode": None,
            "timestamp": None,
            "timestamp_range": None,
            "similarity": 0,
            "frames_agreed": 0,
            "frames_total": frames_total,
            "confident": False,
        }

    winner_id, winning_matches = vote_result
    best = max(winning_matches, key=lambda m: m["similarity%"])
    timestamp, timestamp_range = calc_timestamp(winning_matches, duration_sec)  # ← pass duration
    avg_similarity = int(sum(m["similarity%"] for m in winning_matches) / len(winning_matches))
    frames_agreed = len(winning_matches)
    confident = avg_similarity >= config.CONFIDENT_THRESHOLD

    logger.info(
        "Verdict: %s | ep %s | %s | similarity %d%% | %d/%d frames agreed",
        best.get("English Title"), best.get("Episode"),
        timestamp or timestamp_range, avg_similarity, frames_agreed, frames_total,
    )

    return {
        "found": True,
        "anime": best.get("English Title") or best.get("Romaji") or best.get("Native Title"),
        "episode": best.get("Episode"),
        "timestamp": timestamp,
        "timestamp_range": timestamp_range,
        "similarity": avg_similarity,
        "frames_agreed": frames_agreed,
        "frames_total": frames_total,
        "confident": confident,
        "animelist_id": best.get("animelist_id"),
    }
