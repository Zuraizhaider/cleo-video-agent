"""
handlers/video_handler.py
Full video creation pipeline:
1. Understand request
2. Ask clarification if needed
3. Write director script
4. Show script for approval
5. Generate video options per scene
6. User picks A/B/C per scene
7. Generate voice + merge
8. Send complete clips + script
"""
import asyncio
import os
from telegram import Update
from telegram.ext import ContextTypes
from services.claude_service import (
    understand_request,
    find_trending_topic,
    write_director_script,
    rewrite_script,
    format_script_message,
)
from services.video_service import generate_clip_options
from services.voice_service import generate_voiceover
from services.merge_service import merge_video_audio
from config import CLIPS_PER_SCENE, BOT_NAME

OPTION_LABELS = ["A", "B", "C", "D"]


async def handle_video_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point — understand what user wants and route accordingly."""
    text = update.message.text.strip()

    msg = await update.message.reply_text(
        "🎬 On it! Let me think about this…",
        parse_mode="Markdown"
    )

    try:
        intent_data = understand_request(text)
    except Exception:
        intent_data = {
            "intent": "specific_topic",
            "topic": text,
            "niche": None,
            "description": None,
            "needs_clarification": False,
            "clarification_question": None,
        }

    intent = intent_data.get("intent", "specific_topic")

    # Store for later use
    context.user_data["video_intent"]   = intent_data
    context.user_data["video_state"]    = "clarifying"

    # Scene description — ask clarification
    if intent_data.get("needs_clarification"):
        context.user_data["video_state"] = "awaiting_clarification"
        await msg.edit_text(
            f"🎥 {intent_data.get('clarification_question', 'Full 60s short or single clip?')}",
            parse_mode="Markdown"
        )
        return

    # Find trending topic if none given
    if intent == "find_topic":
        await msg.edit_text("🔍 Searching for trending topics…")
        try:
            topic = find_trending_topic()
        except Exception:
            topic = "5 habits that will change your life"
        context.user_data["video_topic"] = topic
        context.user_data["video_state"] = "awaiting_topic_confirm"
        await msg.edit_text(
            f"🔥 Found a trending topic:\n\n"
            f"*\"{topic}\"*\n\n"
            f"Should I write the full script for this?\n"
            f"Reply *`yes`* or tell me a different topic.",
            parse_mode="Markdown"
        )
        return

    # Specific topic or scene — go straight to script
    topic = intent_data.get("topic") or intent_data.get("description") or text
    niche = intent_data.get("niche") or ""
    context.user_data["video_topic"] = topic
    context.user_data["video_niche"] = niche

    await msg.edit_text("✍️ Writing your director script…")
    await _write_and_show_script(update, context, topic, niche, msg)


async def handle_clarification_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user reply to clarification question."""
    text  = update.message.text.strip().lower()
    topic = context.user_data.get("video_intent", {}).get("description", "")
    niche = context.user_data.get("video_intent", {}).get("niche", "")

    msg = await update.message.reply_text("✍️ Writing your script…")

    if any(w in text for w in ["full", "short", "60", "complete", "whole"]):
        # Full 60s short
        await _write_and_show_script(update, context, topic, niche, msg)
    else:
        # Single scene clip — just generate one clip directly
        context.user_data["video_state"]  = "generating_single"
        context.user_data["video_topic"]  = topic
        context.user_data["single_scene"] = {
            "scene_number": 1,
            "start": 0,
            "end": 6,
            "visual": topic,
            "voiceover": "",
            "director_note": "Cinematic, realistic",
            "kling_prompt": topic,
        }
        await msg.edit_text(
            f"🎬 Generating your clip for:\n_{topic}_\n\n"
            "This will take 2–3 minutes…",
            parse_mode="Markdown"
        )
        await _generate_scene_options(update, context, context.user_data["single_scene"], 1, msg)


async def _write_and_show_script(update, context, topic, niche, msg=None):
    """Write script and show to user for approval."""
    try:
        script = write_director_script(topic=topic, niche=niche)
        context.user_data["current_script"] = script
        context.user_data["video_state"]    = "awaiting_script_approval"

        script_text = format_script_message(script)

        if msg:
            await msg.delete()
        await update.message.reply_text(script_text, parse_mode="Markdown")

    except Exception as e:
        error_text = f"❌ Script writing failed: {str(e)[:100]}"
        if msg:
            await msg.edit_text(error_text)
        else:
            await update.message.reply_text(error_text)


async def handle_script_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User said yes — start generating videos scene by scene."""
    script = context.user_data.get("current_script")
    if not script:
        await update.message.reply_text("⚠️ No script found. Start over with a new video request.")
        return

    scenes = script.get("scenes", [])
    context.user_data["video_state"]      = "selecting_clips"
    context.user_data["scenes"]           = scenes
    context.user_data["selected_clips"]   = {}
    context.user_data["current_scene_idx"] = 0

    await update.message.reply_text(
        f"🎬 *Script approved!*\n\n"
        f"Generating video options for {len(scenes)} scenes.\n"
        f"Each scene gets {CLIPS_PER_SCENE} options for you to choose from.\n\n"
        f"_This will take about {len(scenes) * 2}–{len(scenes) * 4} minutes total…_",
        parse_mode="Markdown"
    )

    # Start with scene 1
    await _generate_scene_options(
        update, context, scenes[0], 1
    )


async def _generate_scene_options(update, context, scene, scene_number, msg=None):
    """Generate video options for one scene and send to user."""
    status_msg = await update.message.reply_text(
        f"⏳ Generating Scene {scene_number} options… (~2 min)",
        parse_mode="Markdown"
    )

    try:
        clip_paths = await generate_clip_options(
            scene=scene,
            scene_number=scene_number,
            num_options=CLIPS_PER_SCENE,
        )

        if not clip_paths:
            await status_msg.edit_text(
                f"❌ Scene {scene_number} generation failed. "
                "Check your Minimax API key and credits."
            )
            return

        # Store options
        context.user_data[f"scene_{scene_number}_options"] = clip_paths
        await status_msg.delete()

        # Send each option as video
        await update.message.reply_text(
            f"🎬 *Scene {scene_number}* ({scene.get('start')}s–{scene.get('end')}s)\n"
            f"_{scene.get('voiceover', ''[:80])}_\n\n"
            f"Choose your favourite:",
            parse_mode="Markdown"
        )

        for i, path in enumerate(clip_paths):
            label = OPTION_LABELS[i]
            with open(path, "rb") as f:
                await update.message.reply_video(
                    video=f,
                    caption=f"Option *{label}*",
                    parse_mode="Markdown",
                )

        await update.message.reply_text(
            f"Reply *A*, *B*, or *C* to choose Scene {scene_number}",
            parse_mode="Markdown"
        )

        context.user_data["current_scene_idx"] = scene_number - 1

    except Exception as e:
        await status_msg.edit_text(f"❌ Error generating Scene {scene_number}: {str(e)[:100]}")


async def handle_clip_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User selected A, B or C for current scene."""
    choice      = update.message.text.strip().upper()
    scene_idx   = context.user_data.get("current_scene_idx", 0)
    scenes      = context.user_data.get("scenes", [])
    scene_number = scene_idx + 1

    options = context.user_data.get(f"scene_{scene_number}_options", [])
    label_map = {OPTION_LABELS[i]: path for i, path in enumerate(options)}

    if choice not in label_map:
        await update.message.reply_text(
            f"Please reply *A*, *B*, or *C* to choose Scene {scene_number}",
            parse_mode="Markdown"
        )
        return

    selected_path = label_map[choice]
    context.user_data["selected_clips"][scene_number] = selected_path

    await update.message.reply_text(
        f"✅ Scene {scene_number} → Option {choice} selected!",
        parse_mode="Markdown"
    )

    # Check if more scenes
    next_idx = scene_idx + 1
    if next_idx < len(scenes):
        context.user_data["current_scene_idx"] = next_idx
        await _generate_scene_options(
            update, context,
            scenes[next_idx],
            next_idx + 1,
        )
    else:
        # All scenes selected — generate voice and merge
        await _finalize_video(update, context)


async def _finalize_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate voice for all scenes, merge, and send final clips."""
    script          = context.user_data.get("current_script", {})
    scenes          = context.user_data.get("scenes", [])
    selected_clips  = context.user_data.get("selected_clips", {})

    msg = await update.message.reply_text(
        "🎙️ Generating your cloned voice for all scenes…",
        parse_mode="Markdown"
    )

    complete_clips = []
    voice_sample   = context.user_data.get("voice_sample_path", "")

    for i, scene in enumerate(scenes):
        scene_number = i + 1
        video_path   = selected_clips.get(scene_number, "")
        voiceover    = scene.get("voiceover", "")

        if not video_path or not os.path.exists(video_path):
            continue

        try:
            # Generate voice
            audio_path = await generate_voiceover(
                text=voiceover,
                scene_number=scene_number,
                voice_sample_path=voice_sample or "/app/voice_sample.mp3",
            )

            # Merge video + voice
            if audio_path and os.path.exists(audio_path):
                complete_path = await merge_video_audio(
                    video_path=video_path,
                    audio_path=audio_path,
                    scene_number=scene_number,
                )
                complete_clips.append((scene_number, complete_path, voiceover))
            else:
                complete_clips.append((scene_number, video_path, voiceover))

        except Exception as e:
            print(f"[video_handler] Scene {scene_number} voice/merge error: {e}")
            complete_clips.append((scene_number, video_path, voiceover))

    await msg.delete()

    # Send all complete clips
    await update.message.reply_text(
        f"🎉 *All {len(complete_clips)} clips ready!*\n\n"
        f"Here are your final scenes with voice:",
        parse_mode="Markdown"
    )

    for scene_number, path, voiceover in complete_clips:
        if os.path.exists(path):
            with open(path, "rb") as f:
                await update.message.reply_video(
                    video=f,
                    caption=f"✅ *Scene {scene_number}*\n_{voiceover[:80]}_",
                    parse_mode="Markdown",
                )

    # Send full script
    script_text = "📝 *Full Script for Captions:*\n\n"
    for scene in scenes:
        script_text += (
            f"*Scene {scene.get('scene_number')}* "
            f"({scene.get('start')}s–{scene.get('end')}s)\n"
            f"{scene.get('voiceover', '')}\n\n"
        )

    await update.message.reply_text(script_text, parse_mode="Markdown")

    await update.message.reply_text(
        "✅ *All done!*\n\n"
        "1️⃣ Open *Ssemble* on your browser\n"
        "2️⃣ Drop all clips in order\n"
        "3️⃣ Add captions from the script above\n"
        "4️⃣ Export and post to YouTube! 🚀\n\n"
        "_Want another video? Just tell me the topic!_",
        parse_mode="Markdown"
    )

    # Reset state
    context.user_data["video_state"] = "idle"
    context.user_data.pop("current_script", None)
    context.user_data.pop("selected_clips", None)
    context.user_data.pop("scenes", None)
