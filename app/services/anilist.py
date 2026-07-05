from __future__ import annotations

import base64
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"
_TIMEOUT = 8.0

# Identify the app instead of httpx's default UA - polite API citizenship,
# and some Cloudflare configurations treat generic python clients worse.
_HEADERS = {
    "User-Agent": "AnimeRS/1.0 (https://github.com/111yoav111)",
    "Accept": "application/json",
}

_QUERY = """
query ($id: Int) {
    Media(id: $id, type: ANIME) {
        coverImage {
            large
        }
        bannerImage
        seasonYear
        description(asHtml: false)
        streamingEpisodes {
            title
            thumbnail
        }
    }
}
"""


def _safe_episode(episode) -> Optional[int]:
    """
    Return a valid episode number for AniList lookups.

    trace.moe episode values may be integers, numeric strings, ranges, or
    lists. Only a single episode number is returned; otherwise None is
    returned so the lookup can be skipped safely.
    """
    if isinstance(episode, bool):
        return None
    if isinstance(episode, int):
        return episode
    if isinstance(episode, str) and episode.isdigit():
        return int(episode)
    return None


def _download_b64(client: httpx.Client, url: str) -> Optional[str]:
    """
    Download an image and return it base64-encoded. None on any failure.
    """
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("ascii")
    except Exception as exc:
        logger.warning("Image download failed (%s): %s", url, exc)
        return None


def enrich(verdict: dict) -> dict:
    """
    Fetch the cover image, release year, episode thumbnail, AniList banner,
    and description for the result.

    Isf metadata can't be fetched, the original verdict
    is returned unchanged.

    Episode thumbnails come from AniList's `streamingEpisodes` list, which
    usually matches the requested episode but isn't guaranteed to.
    """
    animelist_id = verdict.get("animelist_id")
    if not verdict.get("found") or not animelist_id or animelist_id == "Unknown":
        return verdict

    # One client reused for the GraphQL call and every image download.
    # httpx.Client is thread-safe, so the concurrent downloads below can share it.
    with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS) as client:
        try:
            resp = client.post(
                _ANILIST_GRAPHQL_URL,
                json={"query": _QUERY, "variables": {"id": int(animelist_id)}},
            )
            resp.raise_for_status()
            media = resp.json().get("data", {}).get("Media", {}) or {}
        except httpx.HTTPStatusError as exc:
            # AniList explains 403s in the body (e.g. "API temporarily
            # disabled due to stability issues") - log it, don't hide it.
            body = (exc.response.text or "")[:300]
            logger.warning(
                "AniList metadata lookup failed for id=%s: %s | response: %s",
                animelist_id, exc, body,
            )
            return verdict
        except Exception as exc:
            logger.warning("AniList metadata lookup failed for id=%s: %s", animelist_id, exc)
            return verdict

        cover_url = (media.get("coverImage") or {}).get("large")
        banner_url = media.get("bannerImage")
        year = media.get("seasonYear")
        description = media.get("description") or None

        episode_thumb_url = None
        episode_title = None
        episode = _safe_episode(verdict.get("episode"))
        streaming_episodes = media.get("streamingEpisodes") or []
        if episode and 1 <= episode <= len(streaming_episodes):
            episode_data = streaming_episodes[episode - 1]
            episode_thumb_url = episode_data.get("thumbnail")
            episode_title = episode_data.get("title") or None

        # The three images are independent - download them concurrently.
        image_urls = {
            "cover_image_b64": cover_url,
            "episode_thumb_b64": episode_thumb_url,
            "banner_image_b64": banner_url,
        }
        image_urls = {key: url for key, url in image_urls.items() if url}
        if image_urls:
            with ThreadPoolExecutor(max_workers=len(image_urls)) as pool:
                futures = {
                    key: pool.submit(_download_b64, client, url)
                    for key, url in image_urls.items()
                }
                for key, future in futures.items():
                    b64 = future.result()
                    if b64:
                        verdict[key] = b64

    if year:
        verdict["year"] = year
    if description:
        verdict["description"] = description
    if episode_title:
        verdict["episode_title"] = episode_title

    return verdict
