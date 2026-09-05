"""Automatic source discovery from Internet Archive records with an explicit
public-domain/Creative-Commons license marker.

This module deliberately does not scrape protected streaming sites, bypass DRM,
login requirements, paywalls, anti-bot systems, or other access controls.
Only files exposed for direct download by the Internet Archive are considered,
and only records carrying a recognizable CC/public-domain license marker are
accepted.
"""

import json
import re
import time
import urllib.parse
from pathlib import Path

import requests

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"
UA = "AnimeBestMomentBot/2.0"

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".webm", ".mov", ".mkv", ".ogv", ".avi"}
LICENSE_MARKERS = (
    "creativecommons.org",
    "publicdomain",
    "public domain",
    "cc0",
)


def _clean_title(anime):
    title = anime.get("title", {})
    return (
        title.get("english")
        or title.get("romaji")
        or title.get("native")
        or ""
    ).strip()


def _license_text(metadata):
    values = []
    for key in ("licenseurl", "license", "rights"):
        value = metadata.get(key)
        if value:
            values.append(str(value))
    return " ".join(values).casefold()


def _has_acceptable_license(metadata):
    return any(marker in _license_text(metadata) for marker in LICENSE_MARKERS)


def _search_identifiers(query, rows=15):
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "description"],
        "rows": rows,
        "page": 1,
        "output": "json",
    }
    r = requests.get(SEARCH_URL, params=params, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    docs = r.json().get("response", {}).get("docs", [])
    return [d.get("identifier") for d in docs if d.get("identifier")]


def _metadata(identifier):
    r = requests.get(
        METADATA_URL.format(identifier=urllib.parse.quote(identifier, safe="")),
        headers={"User-Agent": UA},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def _pick_video_file(metadata):
    files = metadata.get("files", [])
    candidates = []
    for item in files:
        name = str(item.get("name", ""))
        if Path(name).suffix.casefold() not in VIDEO_EXTENSIONS:
            continue
        size = int(float(item.get("size", 0) or 0))
        if size < 100_000:
            continue
        # Prefer MP4/WebM, then smaller files to keep GitHub Actions practical.
        ext_rank = {".mp4": 0, ".webm": 1, ".m4v": 2, ".mov": 3, ".ogv": 4, ".mkv": 5, ".avi": 6}
        rank = ext_rank.get(Path(name).suffix.casefold(), 99)
        candidates.append((rank, size, name))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


def _title_score(anime_title, record_title):
    a = re.sub(r"[^a-z0-9]+", " ", anime_title.casefold()).strip()
    b = re.sub(r"[^a-z0-9]+", " ", record_title.casefold()).strip()
    if not a or not b:
        return 0
    if a == b:
        return 100
    if a in b or b in a:
        return 80
    aw = set(a.split())
    bw = set(b.split())
    return int(100 * len(aw & bw) / max(1, len(aw)))


def find_video_url(anime):
    """Return a directly downloadable CC/public-domain video URL or None."""
    title = _clean_title(anime)
    if not title:
        return None

    # Search exact title first, then a broader anime/title search.
    queries = [
        f'title:"{title}" AND mediatype:movies',
        f'("{title}" OR title:anime) AND mediatype:movies',
    ]

    identifiers = []
    seen = set()
    for q in queries:
        for identifier in _search_identifiers(q):
            if identifier not in seen:
                seen.add(identifier)
                identifiers.append(identifier)

    ranked = []
    for identifier in identifiers:
        try:
            metadata = _metadata(identifier)
        except Exception as exc:
            print(f"[SOURCE] metadata failed for {identifier}: {exc}")
            continue

        if not _has_acceptable_license(metadata):
            continue

        file_name = _pick_video_file(metadata)
        if not file_name:
            continue

        record_title = str(metadata.get("metadata", {}).get("title", identifier))
        score = _title_score(title, record_title)
        ranked.append((score, identifier, file_name, record_title))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    score, identifier, file_name, record_title = ranked[0]
    if score < 35:
        return None

    encoded_identifier = urllib.parse.quote(identifier, safe="")
    encoded_file = urllib.parse.quote(file_name, safe="/")
    url = DOWNLOAD_URL.format(identifier=encoded_identifier, filename=encoded_file)
    print(f"[SOURCE] Selected: {record_title} | license-approved | score={score} | {url}")
    return url


def download_video(url, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(
        url,
        headers={"User-Agent": UA},
        stream=True,
        timeout=(30, 300),
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as out:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    out.write(chunk)

    if destination.stat().st_size < 100_000:
        raise RuntimeError("Downloaded video is unexpectedly small")
