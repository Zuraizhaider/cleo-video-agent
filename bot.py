"""
Cleo — YouTube Shorts Video Agent
Telegram bot that creates AI videos from natural language requests.
Deploy on Railway.
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
    handle_script_approval,
    handle_clip_selection,
)
from handlers.voice_handler import handle_voice_sample
from config import BOT_TOKEN, BOT_NAME

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

HELP_TEXT = f"""
🎬 *{BOT_NAME} — YouTube Shorts Video Agent*

Just talk to me naturally:

*"Hey {BOT_NAME} find a perfect story lets create a video"*
→ I find a trending topic and write the script

*"Hey {BOT_NAME} make a video on morning routines for fitness"*
→ I write a targeted script for your topic and niche

*"Hey {BOT_NAME} make a video of a girl jogging at sunrise"*
→ I ask if you want a full short or single clip

*During script review:*
• *`yes`* — approve and start generating videos
• *`rewrite`* — completely new script
• *`rewrite [instruction]`* — rewrite with your angle

*During scene selection:*
• *`A`*, *`B`*, or *`C`* — choose your favourite clip

*Setup your voice clone:*
Send me a voice message (20–30 seconds of you talking)
→ I clone your voice for all future videos

*Commands:*
/start — Welcome message
/help — Show this menu
/voice — Instructions for voice setup
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"👋 Hey {name}! I am *{BOT_NAME}*, your YouTube Shorts video agent.\n\n"
        f"Tell me a topic and I will create a full cinematic short for you — "
        f"script, video, voice, everything.\n\n"
        + HELP_TEXT,
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎙️ *Voice Clone Setup*\n\n"
        "Send me a voice message of you talking naturally for 20–30 seconds.\n\n"
        "Tips for best results:\n"
        "• Speak clearly and naturally\n"
        "• Use your normal talking voice\n"
        "• No background noise\n"
        "• Say anything — read a paragraph, talk about your day\n\n"
        "Once saved, your cloned voice will be used in every video automatically!",
        parse_mode="Markdown"
    )


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all text messages based on current state."""
    text  = update.message.text.strip()
    lower = text.lower()
    state = context.user_data.get("video_state", "idle")

    # ── Awaiting clarification (full short vs single clip) ────────────────
    if state == "awaiting_clarification":
        await handle_clarification_reply(update, context)
        return

    # ── Awaiting topic confirmation (bot found trending topic) ────────────
    if state == "awaiting_topic_confirm":
        if any(w in lower for w in ["yes", "go", "ok", "sure", "do it", "perfect"]):
            topic = context.user_data.get("video_topic", "")
            niche = context.user_data.get("video_niche", "")
            msg   = await update.message.reply_text("✍️ Writing your director script…")
            from handlers.video_handler import _write_and_show_script
            await _write_and_show_script(update, context, topic, niche, msg)
        else:
            # User gave a different topic
            context.user_data["video_topic"] = text
            context.user_data["video_state"] = "idle"
            msg = await update.message.reply_text("✍️ Writing your director script…")
            from handlers.video_handler import _write_and_show_script
            await _write_and_show_script(update, context, text, "", msg)
        return

    # ── Script approval ───────────────────────────────────────────────────
    if state == "awaiting_script_approval":
        if lower in ["yes", "go", "ok", "looks good", "perfect", "send it", "generate"]:
            await handle_script_approval(update, context)
        elif lower.startswith("rewrite"):
            instruction = lower.replace("rewrite", "").strip()
            msg = await update.message.reply_text("✍️ Rewriting script…")
            try:
                from services.claude_service import rewrite_script, format_script_message
                original = context.user_data.get("current_script", {})
                new_script = rewrite_script(original, instruction)
                context.user_data["current_script"] = new_script
                await msg.delete()
                await update.message.reply_text(
                    format_script_message(new_script),
                    parse_mode="Markdown"
                )
            except Exception as e:
                await msg.edit_text(f"❌ Rewrite failed: {str(e)[:100]}")
        else:
            await update.message.reply_text(
                "Reply *`yes`* to generate videos or *`rewrite`* for a new script.",
                parse_mode="Markdown"
            )
        return

    # ── Scene clip selection A/B/C ────────────────────────────────────────
    if state == "selecting_clips":
        if upper := text.upper() in ["A", "B", "C", "D"]:
            await handle_clip_selection(update, context)
        elif text.upper() in ["A", "B", "C", "D"]:
            await handle_clip_selection(update, context)
        else:
            scene_idx = context.user_data.get("current_scene_idx", 0) + 1
            await update.message.reply_text(
                f"Please reply *A*, *B*, or *C* to choose Scene {scene_idx}",
                parse_mode="Markdown"
            )
        return

    # ── New video request — any state ─────────────────────────────────────
    bot_name_lower = BOT_NAME.lower()
    is_video_request = any(w in lower for w in [
        bot_name_lower, "make a video", "create a video", "find a story",
        "lets create", "make video", "video on", "short on", "create short"
    ])

    if is_video_request:
        await handle_video_request(update, context)
    else:
        await update.message.reply_text(
            f"🎬 Tell me what video to create!\n\n"
            f"Try: *\"Hey {BOT_NAME} make a video on morning routines\"*\n"
            f"Or: *\"Hey {BOT_NAME} find a trending story\"*\n\n"
            f"Type /help for all options.",
            parse_mode="Markdown"
        )


async def route_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages — save as voice clone sample."""
    await handle_voice_sample(update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, route_message
    ))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO, route_voice
    ))

    logger.info(f"{BOT_NAME} starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
