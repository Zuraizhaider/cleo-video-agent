"""
services/voice_service.py
Saves user voice recording for cloning.
Actual voice generation is handled by elevenlabs_service.py
"""
import os
import aiofiles


async def save_voice_sample(audio_bytes: bytes, filename: str = "voice_sample.mp3") -> str:
    """Save user voice recording to disk for cloning reference."""
    os.makedirs("/app", exist_ok=True)
    sample_path = f"/app/{filename}"
    async with aiofiles.open(sample_path, "wb") as f:
        await f.write(audio_bytes)
    return sample_path
