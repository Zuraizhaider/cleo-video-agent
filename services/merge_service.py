"""
services/merge_service.py
Merges video clip + voice audio into one complete MP4 using FFmpeg.
FFmpeg is free and runs on Railway.
"""
import asyncio
import os


async def merge_video_audio(
    video_path: str,
    audio_path: str,
    scene_number: int,
) -> str:
    """
    Merge video + audio into one complete MP4.
    Returns path to merged file.
    """
    output_path = f"/tmp/scene{scene_number}_complete.mp4"

    cmd = [
        "ffmpeg",
        "-y",                     # overwrite if exists
        "-i", video_path,         # video input
        "-i", audio_path,         # audio input
        "-c:v", "copy",           # copy video stream (no re-encode)
        "-c:a", "aac",            # encode audio as AAC
        "-shortest",              # end at shortest stream
        "-map", "0:v:0",          # take video from first input
        "-map", "1:a:0",          # take audio from second input
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()

    if os.path.exists(output_path):
        return output_path
    raise Exception(f"FFmpeg merge failed for scene {scene_number}")


async def merge_all_scenes(scene_files: list[str]) -> str:
    """
    Optionally concatenate all scene clips into one final video.
    Returns path to final video.
    (User can also do this manually in Ssemble)
    """
    if not scene_files:
        raise Exception("No scene files to merge")

    # Write concat file
    concat_path = "/tmp/concat_list.txt"
    with open(concat_path, "w") as f:
        for path in scene_files:
            f.write(f"file '{path}'\n")

    output_path = "/tmp/final_short.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_path,
        "-c", "copy",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()

    if os.path.exists(output_path):
        return output_path
    raise Exception("FFmpeg concat failed")
