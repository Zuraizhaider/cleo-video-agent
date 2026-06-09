"""
services/voice_service.py
ElevenLabs voice cloning — real cloned voice at speed 1.4
Falls back to gTTS if no ElevenLabs key.
"""
import os
import aiohttp
import asyncio
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, VOICE_SPEED

OUTPUT_DIR = "/tmp/voice_outputs"


def _ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


async def generate_voiceover(
    text: str,
    scene_number: int,
    style: str = "",
) -> str:
    """
    Generate voiceover for a scene.
    Uses ElevenLabs if key available, else gTTS fallback.
    Returns path to MP3 file.
    """
    _ensure_dir()
    output_path = f"{OUTPUT_DIR}/scene{scene_number}_voice.mp3"

    if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
        return await _elevenlabs_tts(text, output_path, style)
    else:
        return await _gtts_fallback(text, output_path)


async def _elevenlabs_tts(text: str, output_path: str, style: str = "") -> str:
    """Generate voice using ElevenLabs API with cloned voice."""

    # Map style to ElevenLabs settings
    style_settings = {
        "excited":    {"stability": 0.3, "similarity_boost": 0.8, "style": 0.8},
        "calm":       {"stability": 0.8, "similarity_boost": 0.7, "style": 0.2},
        "aggressive": {"stability": 0.2, "similarity_boost": 0.9, "style": 0.9},
        "whisper":    {"stability": 0.9, "similarity_boost": 0.6, "style": 0.1},
        "deep":       {"stability": 0.6, "similarity_boost": 0.8, "style": 0.4},
        "":           {"stability": 0.5, "similarity_boost": 0.8, "style": 0.5},
    }

    settings = style_settings.get(style.lower(), style_settings[""])

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
            "speed":            VOICE_SPEED,
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    audio = await resp.read()
                    with open(output_path, "wb") as f:
                        f.write(audio)
                    return output_path
                else:
                    error = await resp.text()
                    print(f"[voice] ElevenLabs error {resp.status}: {error}")
                    return await _gtts_fallback(text, output_path)
    except Exception as e:
        print(f"[voice] ElevenLabs exception: {e}")
        return await _gtts_fallback(text, output_path)


async def _gtts_fallback(text: str, output_path: str) -> str:
    """Google TTS fallback — free, decent quality."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _gtts_sync, text, output_path)
        return output_path
    except Exception as e:
        print(f"[voice] gTTS error: {e}")
        return ""


def _gtts_sync(text: str, output_path: str):
    from gtts import gTTS
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(output_path)
