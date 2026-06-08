"""
handlers/voice_handler.py
Handles user sending a voice recording for cloning.
"""
from telegram import Update
from telegram.ext import ContextTypes
from services.voice_service import save_voice_sample


async def handle_voice_sample(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sends a voice message — save it as their clone sample."""
    msg = await update.message.reply_text(
        "🎙️ Saving your voice sample for cloning…"
    )

    try:
        voice = update.message.voice or update.message.audio
        if not voice:
            await msg.edit_text("⚠️ Please send a voice message or audio file.")
            return

        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()

        sample_path = await save_voice_sample(bytes(audio_bytes))
        context.user_data["voice_sample_path"] = sample_path

        await msg.edit_text(
            "✅ *Voice sample saved!*\n\n"
            "Your cloned voice will be used in all future videos.\n\n"
            "Now just tell me a topic and I will create your video! 🎬",
            parse_mode="Markdown"
        )

    except Exception as e:
        await msg.edit_text(f"❌ Error saving voice sample: {str(e)[:100]}")
