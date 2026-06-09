"""
Configuration — all secrets from Railway environment variables.
"""
import os

# ── Telegram ──────────────────────────────────────────────
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# ── Anthropic (Claude) ────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Minimax / Hailuo AI ───────────────────────────────────
MINIMAX_API_KEY  = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")

# ── ElevenLabs voice clone ────────────────────────────────
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
VOICE_SPEED         = float(os.getenv("VOICE_SPEED", "1.4"))

# ── Video settings ────────────────────────────────────────
CLIPS_PER_SCENE = int(os.getenv("CLIPS_PER_SCENE", "3"))
SCENE_DURATION  = int(os.getenv("SCENE_DURATION", "5"))

# ── Bot name ──────────────────────────────────────────────
BOT_NAME = os.getenv("BOT_NAME", "Cleo")
