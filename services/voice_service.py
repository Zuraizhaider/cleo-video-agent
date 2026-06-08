"""
services/voice_service.py
Clones user voice using OpenVoice V2 (free, runs on Railway).
Generates voiceover audio for each scene.
"""
import os
import asyncio
import aiofiles
from pathlib import Path

VOICE_SAMPLE_PATH = os.getenv("VOICE_SAMPLE_PATH", "/app/voice_sample.mp3")
OUTPUT_DIR        = "/tmp/voice_outputs"


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


async def generate_voiceover(
    text: str,
    scene_number: int,
    voice_sample_path: str = VOICE_SAMPLE_PATH,
) -> str:
    """
    Generate cloned voice audio for a scene.
    Returns path to generated MP3 file.
    """
    _ensure_output_dir()
    output_path = f"{OUTPUT_DIR}/scene{scene_number}_voice.mp3"

    # Run OpenVoice in a thread (CPU-bound)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _generate_with_openvoice,
        text,
        voice_sample_path,
        output_path,
    )
    return result


def _generate_with_openvoice(
    text: str,
    voice_sample_path: str,
    output_path: str,
) -> str:
    """
    Run OpenVoice V2 voice cloning synchronously.
    Falls back to basic TTS if OpenVoice not installed.
    """
    try:
        # Try OpenVoice V2
        from openvoice import se_extractor
        from openvoice.api import ToneColorConverter
        import torch
        from melo.api import TTS

        device = "cpu"  # Railway uses CPU

        # Generate base TTS
        tts_model = TTS(language="EN", device=device)
        speaker_ids = tts_model.hps.data.spk2id
        speaker_key = list(speaker_ids.keys())[0]
        speaker_id  = speaker_ids[speaker_key]

        base_audio = output_path.replace(".mp3", "_base.wav")
        tts_model.tts_to_file(
            text,
            speaker_id,
            base_audio,
            speed=1.0,
        )

        # Apply voice cloning
        if os.path.exists(voice_sample_path):
            ckpt_converter = "checkpoints_v2/converter"
            converter = ToneColorConverter(
                f"{ckpt_converter}/config.json", device=device
            )
            converter.load_ckpt(f"{ckpt_converter}/checkpoint.pth")

            target_se, _ = se_extractor.get_se(
                voice_sample_path,
                converter,
                vad=False,
            )
            source_se = torch.load(
                f"checkpoints_v2/base_speakers/ses/{speaker_key.lower()}.pth",
                map_location=device,
            )

            converter.convert(
                audio_src_path=base_audio,
                src_se=source_se,
                tgt_se=target_se,
                output_path=output_path,
                message="@MyShell",
            )
        else:
            # No voice sample — use base TTS
            import shutil
            shutil.copy(base_audio, output_path)

        return output_path

    except ImportError:
        # OpenVoice not installed — use pyttsx3 fallback
        return _fallback_tts(text, output_path)
    except Exception as e:
        print(f"[voice_service] OpenVoice error: {e}")
        return _fallback_tts(text, output_path)


def _fallback_tts(text: str, output_path: str) -> str:
    """Basic TTS fallback using gTTS (Google Text to Speech — free)."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        mp3_path = output_path if output_path.endswith(".mp3") else output_path + ".mp3"
        tts.save(mp3_path)
        return mp3_path
    except Exception as e:
        print(f"[voice_service] gTTS fallback error: {e}")
        return ""


async def save_voice_sample(audio_bytes: bytes, filename: str = "voice_sample.mp3") -> str:
    """Save user's voice recording for cloning."""
    sample_path = f"/app/{filename}"
    os.makedirs("/app", exist_ok=True)
    async with aiofiles.open(sample_path, "wb") as f:
        await f.write(audio_bytes)
    return sample_path
