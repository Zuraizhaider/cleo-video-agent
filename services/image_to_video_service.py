"""
services/image_to_video_service.py
Handles product ad generation via Minimax image-to-video API.
Supports both real product photos and text-only demo generation.
"""
import aiohttp
import asyncio
import os
import base64
import time
from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID

MINIMAX_BASE = "https://api.minimaxi.chat/v1"


async def generate_product_ad(
    prompt: str,
    image_path: str = None,
    duration: int = 6,
) -> str:
    """
    Generate a product ad clip.
    - If image_path provided: image-to-video (animate real product)
    - If no image: text-to-video (generate demo product)
    Returns local file path of downloaded video.
    """
    if not MINIMAX_API_KEY:
        raise Exception(
            "Video generation needs your Minimax API key.\n"
            "Add MINIMAX_API_KEY in Railway Variables."
        )

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }

    if image_path and os.path.exists(image_path):
        # Image-to-video: animate real product photo
        payload = await _build_image_to_video_payload(
            prompt, image_path, duration
        )
        endpoint = f"{MINIMAX_BASE}/video_generation"
    else:
        # Text-to-video: generate demo product from scratch
        payload = {
            "model": "video-01",
            "prompt": prompt,
            "duration": duration,
            "resolution": "1080x1920",
            "fps": 24,
        }
        endpoint = f"{MINIMAX_BASE}/video_generation"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await resp.json()
            task_id = data.get("task_id")
            if not task_id:
                raise Exception(f"No task_id returned: {data}")

        video_url = await _poll_task(session, task_id, headers)

        output_path = "/tmp/product_ad.mp4"
        async with session.get(
            video_url,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as r:
            with open(output_path, "wb") as f:
                f.write(await r.read())

    return output_path


async def _build_image_to_video_payload(
    prompt: str,
    image_path: str,
    duration: int,
) -> dict:
    """Build image-to-video API payload with base64 encoded image."""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = image_path.split(".")[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp"}
    mime = mime_map.get(ext, "image/jpeg")

    return {
        "model": "video-01",
        "prompt": prompt,
        "duration": duration,
        "resolution": "1080x1920",
        "fps": 24,
        "first_frame_image": f"data:{mime};base64,{image_data}",
    }


async def _poll_task(
    session: aiohttp.ClientSession,
    task_id: str,
    headers: dict,
    max_wait: int = 360,
) -> str:
    """Poll until task complete. Returns download URL."""
    start = time.time()
    while time.time() - start < max_wait:
        async with session.get(
            f"{MINIMAX_BASE}/query/video_generation",
            params={"task_id": task_id},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data   = await resp.json()
            status = data.get("status", "")
            if status == "Success":
                file_id = data.get("file_id", "")
                return await _get_download_url(session, file_id, headers)
            elif status in ["Failed", "Expired"]:
                raise Exception(f"Task failed: {data}")
        await asyncio.sleep(10)
    raise Exception("Video generation timed out after 6 minutes")


async def _get_download_url(
    session: aiohttp.ClientSession,
    file_id: str,
    headers: dict,
) -> str:
    """Get download URL from file_id."""
    async with session.get(
        f"{MINIMAX_BASE}/files/retrieve",
        params={"file_id": file_id, "GroupId": MINIMAX_GROUP_ID},
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=15),
    ) as resp:
        data = await resp.json()
        url  = data.get("file", {}).get("download_url", "")
        if not url:
            raise Exception(f"No download URL: {data}")
        return url
