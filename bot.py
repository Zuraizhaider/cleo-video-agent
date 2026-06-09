"""
Cleo v3 — YouTube Shorts Video Agent
Clean, natural, no command list shown.
"""
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)
from handlers.video_handler import (
    handle_video_request,
    handle_clarification_reply,
    handle_script_commands,
    handle_script_approval,
    handle_clip_selection,
)
from handlers.voice_handler import handle_voice_sample
from config import BOT_TOKEN, BOT_NAME, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY, MINIMAX_API_KEY

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"👋 Hey {name}! I am *{BOT_NAME}*.\n\n"
        "Tell me what video you want and I will create it.",
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎬 *{BOT_NAME} — How to use*\n\n"
        "Just talk to me naturally:\n\n"
        "_\"make a video on morning routines for fitness\"_\n"
        "_\"find a perfect story and create a video\"_\n"
        "_\"make a funny parrot video\"_\n"
        "_\"make a creepy story video\"_\n"
        "_\"make a video of a girl dancing on a balcony\"_\n\n"
        "*During script review:*\n"
        "• `yes` — generate videos\n"
        "• `rewrite` — new script\n"
        "• `rewrite scene 2 prompt` — fix one scene\n"
        "• `edit scene 3 prompt: [your text]` — your own prompt\n"
        "• `show prompts` / `hide prompts` — toggle prompts\n"
        "• `slow` / `fast` / `deep` / `calm` / `creepy` — voice style\n\n"
        "*During scene selection:*\n"
        "• `A`, `B` or `C` — pick your clip\n\n"
        "*Series:*\n"
        "• `part 2`, `part 3` — continue story\n\n"
        "*Voice clone:*\n"
        "Send a voice message — I clone it for all videos\n\n"
        "/status — check API keys",
        parse_mode="Markdown"
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    anthropic  = "✅ Ready" if ANTHROPIC_API_KEY else "❌ Add ANTHROPIC_API_KEY in Railway"
    minimax    = "✅ Ready" if MINIMAX_API_KEY   else "❌ Add MINIMAX_API_KEY in Railway"
    elevenlabs = "✅ Ready" if ELEVENLABS_API_KEY else "⚠️ Add ELEVENLABS_API_KEY (using gTTS now)"
    voice      = "✅ Saved" if context.user_data.get("voice_sample_path") else "⚠️ Send a voice message to set up"

    await update.message.reply_text(
        f"📊 *{BOT_NAME} Status*\n\n"
        f"🧠 Anthropic: {anthropic}\n"
        f"🎬 Minimax: {minimax}\n"
        f"🎙️ ElevenLabs: {elevenlabs}\n"
        f"🎤 Voice sample: {voice}",
        parse_mode="Markdown"
    )


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text  = update.message.text.strip()
    lower = text.lower()
    state = context.user_data.get("video_state", "idle")

    # Awaiting clarification
    if state == "awaiting_clarification":
        await handle_clarification_reply(update, context)
        return

    # Awaiting topic confirmation
    if state == "awaiting_topic_confirm":
        if any(w in lower for w in ["yes", "go", "ok", "sure", "perfect", "great", "do it"]):
            topic = context.user_data.get("video_topic", "")
            niche = context.user_data.get("video_niche", "")
            msg   = await update.message.reply_text("✍️ Writing director script…")
            from handlers.video_handler import _write_and_show_script
            await _write_and_show_script(update, context, topic, niche, msg)
        else:
            context.user_data["video_topic"] = text
            context.user_data["video_state"] = "idle"
            msg = await update.message.reply_text("✍️ Writing director script…")
            from handlers.video_handler import _write_and_show_script
            await _write_and_show_script(update, context, text, "", msg)
        return

    # Script approval — all commands handled here
    if state == "awaiting_script_approval":
        await handle_script_commands(update, context)
        return

    # Scene clip selection
    if state == "selecting_clips":
        if text.upper() in ["A", "B", "C", "D"]:
            await handle_clip_selection(update, context)
        else:
            scene_num = context.user_data.get("current_scene_idx", 0) + 1
            await update.message.reply_text(
                f"Reply *A*, *B* or *C* for Scene {scene_num}",
                parse_mode="Markdown"
            )
        return

    # Series continuation from idle
    if lower.startswith("part ") and len(lower.split()) > 1 and lower.split()[1].isdigit():
        await handle_video_request(update, context)
        return

    # New video request — detect naturally
    bot_lower  = BOT_NAME.lower()
    is_request = any(w in lower for w in [
        bot_lower, "make a video", "create a video", "find a story",
        "lets create", "make video", "video on", "short on",
        "create short", "find a perfect", "make a short",
        "create a short", "make me a video", "funny video",
        "create video", "make an", "create an",
    ])

    if is_request:
        await handle_video_request(update, context)
    else:
        await update.message.reply_text(
            "Tell me what video you want and I will create it. 🎬"
        )


async def route_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_voice_sample(update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, route_voice))
    logger.info(f"{BOT_NAME} v3 starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
