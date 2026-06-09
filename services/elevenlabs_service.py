"""
services/elevenlabs_service.py
ElevenLabs voice — natural speed by default.
Speed/style only applied when user specifies.
"""
import aiohttp
import asyncio
import os
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

OUTPUT_DIR = "/tmp/voice_outputs"

VOICE_STYLES = {
    "slow":    {"stability": 0.7, "similarity_boost": 0.85, "style": 0.2, "speed": 0.75},
    "fast":    {"stability": 0.4, "similarity_boost": 0.80, "style": 0.3, "speed": 1.4},
    "deep":    {"stability": 0.8, "similarity_boost": 0.90, "style": 0.1, "speed": 0.9},
    "calm":    {"stability": 0.9, "similarity_boost": 0.85, "style": 0.0, "speed": 0.85},
    "excited": {"stability": 0.3, "similarity_boost": 0.75, "style": 0.8, "speed": 1.2},
    "creepy":  {"stability": 0.6, "similarity_boost": 0.70, "style": 0.5, "speed": 0.7},
    "natural": {"stability": 0.5, "similarity_boost": 0.85, "style": 0.3, "speed": 1.0},
}


def _ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


async def generate_voiceover(
    text: str,
    scene_number: int,
    voice_style: str = "natural",
) -> str:
    """
    Generate voiceover. Speed and style only applied if voice_style specified.
    Default is natural — no modification.
    """
    _ensure_dir()
    output_path = f"{OUTPUT_DIR}/scene{scene_number}_voice.mp3"

    if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
        try:
            return await _elevenlabs_tts(text, output_path, voice_style)
        except Exception as e:
            print(f"[elevenlabs] Error: {e} — using gTTS")

    return await _gtts_fallback(text, output_path)


async def _elevenlabs_tts(
    text: str,
    output_path: str,
    voice_style: str = "natural",
) -> str:
    settings = VOICE_STYLES.get(voice_style, VOICE_STYLES["natural"])
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability":        settings["stability"],
            "similarity_boost": settings["similarity_boost"],
            "style":            settings["style"],
            "use_speaker_boost": True,
            "speed":            settings["speed"],
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
                return output_path
            raise Exception(f"ElevenLabs {resp.status}: {(await resp.text())[:100]}")


async def _gtts_fallback(text: str, output_path: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _gtts_sync, text, output_path)


def _gtts_sync(text: str, output_path: str) -> str:
    try:
        from gtts import gTTS
        gTTS(text=text, lang="en", slow=False).save(output_path)
        return output_path
    except Exception as e:
        print(f"[gtts] {e}")
        return ""
