"""
services/video_service.py
Generates video clips using Minimax Hailuo AI API.
Sends same prompt multiple times to get options to choose from.
"""
import aiohttp
import asyncio
import os
import time
from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID, CLIPS_PER_SCENE


MINIMAX_BASE = "https://api.minimaxi.chat/v1"


async def generate_clip_options(
    scene: dict,
    scene_number: int,
    num_options: int = 3,
) -> list[str]:
    """
    Generate [num_options] video clips for a scene.
    Returns list of local file paths.
    """
    prompt    = scene.get("kling_prompt") or scene.get("visual", "")
    duration  = min(scene.get("end", 5) - scene.get("start", 0), 6)  # Minimax max 6s

    tasks = [
        _generate_single_clip(
            prompt=prompt,
            duration=duration,
            scene_number=scene_number,
            option_index=i,
        )
        for i in range(num_options)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    paths   = [r for r in results if isinstance(r, str) and os.path.exists(r)]
    return paths


async def _generate_single_clip(
    prompt: str,
    duration: int,
    scene_number: int,
    option_index: int,
) -> str:
    """
    Submit a video generation task and poll until complete.
    Returns local file path of downloaded video.
    """
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }

    # Add slight variation to prompt for each option
    variations = [
        "",
        " Slightly different camera angle and lighting.",
        " Different mood and color grading.",
    ]
    varied_prompt = prompt + variations[option_index % len(variations)]

    payload = {
        "model": "video-01",
        "prompt": varied_prompt,
        "duration": duration,
        "resolution": "1080x1920",  # vertical for Shorts
        "fps": 24,
    }

    async with aiohttp.ClientSession() as session:
        # Submit task
        async with session.post(
            f"{MINIMAX_BASE}/video_generation",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await resp.json()
            task_id = data.get("task_id")
            if not task_id:
                raise Exception(f"No task_id returned: {data}")

        # Poll for completion
        video_url = await _poll_task(session, task_id, headers)

        # Download video
        output_path = f"/tmp/scene{scene_number}_option{option_index + 1}.mp4"
        async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=60)) as r:
            with open(output_path, "wb") as f:
                f.write(await r.read())

        return output_path


async def _poll_task(
    session: aiohttp.ClientSession,
    task_id: str,
    headers: dict,
    max_wait: int = 300,
) -> str:
    """Poll Minimax task until complete. Returns video URL."""
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
                return data["file_id"]  # URL or file ID
            elif status in ["Failed", "Expired"]:
                raise Exception(f"Task failed: {data}")

        await asyncio.sleep(10)  # check every 10 seconds

    raise Exception("Video generation timed out after 5 minutes")


async def get_video_url_from_file_id(file_id: str) -> str:
    """Convert Minimax file_id to downloadable URL."""
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MINIMAX_BASE}/files/retrieve",
            params={"file_id": file_id, "GroupId": MINIMAX_GROUP_ID},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
            return data.get("file", {}).get("download_url", "")
