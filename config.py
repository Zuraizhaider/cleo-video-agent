"""
Configuration — all secrets from Railway environment variables.
"""
import os

# ── Telegram ──────────────────────────────────────────────
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# ── Anthropic (Claude) ────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "placeholder")

# ── Minimax / Hailuo AI ───────────────────────────────────
MINIMAX_API_KEY  = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")

# ── Video settings ────────────────────────────────────────
CLIPS_PER_SCENE  = int(os.getenv("CLIPS_PER_SCENE", "3"))   # options to choose from
SCENE_DURATION   = int(os.getenv("SCENE_DURATION", "5"))     # seconds per scene clip

# ── Voice clone ───────────────────────────────────────────
VOICE_SAMPLE_PATH = os.getenv("VOICE_SAMPLE_PATH", "/app/voice_sample.mp3")

# ── Bot name ──────────────────────────────────────────────
BOT_NAME = os.getenv("BOT_NAME", "Cleo")
