import os
import time
import requests

GRAPH = os.getenv("GRAPH_API_VERSION", "v23.0")
TOKEN = os.environ["INSTAGRAM_ACCESS_TOKEN"]
USER = os.environ["INSTAGRAM_USER_ID"]


def publish_reel(video_url, caption):
    base = f"https://graph.facebook.com/{GRAPH}"

    response = requests.post(
        f"{base}/{USER}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": TOKEN,
        },
        timeout=60,
    )
    response.raise_for_status()
    creation_id = response.json().get("id")
    if not creation_id:
        raise RuntimeError(f"No Instagram creation ID: {response.text}")

    deadline = time.time() + 900
    while time.time() < deadline:
        status = requests.get(
            f"{base}/{creation_id}",
            params={
                "fields": "status_code,status",
                "access_token": TOKEN,
            },
            timeout=60,
        )
        status.raise_for_status()
        data = status.json()
        code = str(data.get("status_code", "")).upper()
        print("[INSTAGRAM] status:", code or data.get("status"), flush=True)
        if code in {"FINISHED", "PUBLISHED"}:
            break
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(str(data))
        time.sleep(15)
    else:
        raise RuntimeError("Instagram processing timed out")

    published = requests.post(
        f"{base}/{USER}/media_publish",
        data={"creation_id": creation_id, "access_token": TOKEN},
        timeout=60,
    )
    published.raise_for_status()
    media_id = published.json().get("id")
    if not media_id:
        raise RuntimeError(f"No published media ID: {published.text}")
    return media_id
