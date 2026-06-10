"""
handlers/video_handler.py
Full pipeline with prompt visibility and per-scene prompt editing.
"""
import asyncio
import os
from telegram import Update
from telegram.ext import ContextTypes
from services.claude_service import (
    understand_request, find_trending_topic,
    write_director_script, rewrite_script,
    rewrite_scene_prompt, format_script_message,
    generate_story_options, format_story_options,
)
from services.video_service import generate_clip_options
from services.elevenlabs_service import generate_voiceover
from services.merge_service import merge_video_audio
from config import CLIPS_PER_SCENE, BOT_NAME

OPTION_LABELS = ["A", "B", "C", "D"]


async def handle_video_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    msg  = await update.message.reply_text("🎬 On it…")

    try:
        intent_data = understand_request(text)
    except Exception as e:
        await msg.edit_text(f"⚠️ {str(e)}")
        return

    context.user_data["video_intent"] = intent_data
    context.user_data["video_state"]  = "thinking"
    context.user_data["show_prompts"] = True
    context.user_data["voice_style"]  = intent_data.get("voice_style") or "natural"

    intent      = intent_data.get("intent", "specific_topic")
    needs_voice = intent_data.get("needs_voice", True)
    is_series   = intent_data.get("is_series", False)
    series_part = intent_data.get("series_part", 1)

    # Series continuation — skip story options
    if is_series and series_part > 1:
        prev  = context.user_data.get("series_summary", "")
        topic = intent_data.get("topic") or context.user_data.get("video_topic", "")
        niche = intent_data.get("niche") or context.user_data.get("video_niche", "")
        style = intent_data.get("style") or context.user_data.get("video_style", "")
        await msg.edit_text(f"✍️ Writing Part {series_part}…")
        await _write_and_show_script(
            update, context, topic, niche, msg,
            needs_voice=needs_voice, style=style,
            series_part=series_part, previous_summary=prev,
        )
        return

    # Find trending topic first
    if intent == "find_topic":
        await msg.edit_text("🔍 Finding trending topic…")
        try:
            topic = find_trending_topic()
        except Exception as e:
            await msg.edit_text(f"⚠️ {str(e)}")
            return
    else:
        topic = intent_data.get("topic") or intent_data.get("description") or text

    niche = intent_data.get("niche") or ""
    style = intent_data.get("style") or ""

    context.user_data["video_topic"]  = topic
    context.user_data["video_niche"]  = niche
    context.user_data["video_style"]  = style
    context.user_data["needs_voice"]  = needs_voice
    context.user_data["pending_queue"] = []

    # Generate 3 story options
    await msg.edit_text("💡 Creating story ideas…")
    try:
        options = generate_story_options(topic, niche, style, count=3)
        context.user_data["story_options"] = options
        context.user_data["video_state"]   = "awaiting_story_selection"
        await msg.delete()
        await update.message.reply_text(
            format_story_options(options, topic),
            parse_mode="Markdown"
        )
    except Exception as e:
        await msg.edit_text(f"⚠️ {str(e)}")


async def handle_clarification_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text  = update.message.text.strip().lower()
    topic = context.user_data.get("video_intent", {}).get("description", "")
    niche = context.user_data.get("video_intent", {}).get("niche", "")
    msg   = await update.message.reply_text("✍️ Writing script…")

    needs_voice = any(w in text for w in ["full", "short", "60", "yes", "complete"])
    await _write_and_show_script(
        update, context, topic, niche, msg, needs_voice=needs_voice
    )


async def _write_and_show_script(
    update, context, topic, niche, msg=None,
    needs_voice=True, style="",
    series_part=1, previous_summary="",
):
    voice_style = context.user_data.get("voice_style", "natural")
    show_prompts = context.user_data.get("show_prompts", True)
    try:
        script = write_director_script(
            topic=topic, niche=niche, style=style,
            needs_voice=needs_voice,
            series_part=series_part,
            previous_summary=previous_summary,
            voice_style=voice_style if voice_style != "natural" else "",
        )
        context.user_data["current_script"] = script
        context.user_data["video_state"]    = "awaiting_script_approval"
        context.user_data["needs_voice"]    = needs_voice
        context.user_data["video_style"]    = script.get("style", "ugc")

        if msg:
            await msg.delete()
        await update.message.reply_text(
            format_script_message(script, show_prompts=show_prompts),
            parse_mode="Markdown"
        )
    except Exception as e:
        err = f"⚠️ {str(e)}"
        if msg:
            await msg.edit_text(err)
        else:
            await update.message.reply_text(err)


async def handle_script_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all commands during script approval state."""
    text  = update.message.text.strip()
    lower = text.lower()
    script = context.user_data.get("current_script", {})
    style  = context.user_data.get("video_style", "ugc")
    show_prompts = context.user_data.get("show_prompts", True)

    # YES — approve
    if any(w in lower for w in ["yes", "go", "ok", "looks good", "perfect", "generate", "send it", "approve"]):
        await handle_script_approval(update, context)
        return

    # HIDE PROMPTS
    if lower == "hide prompts":
        context.user_data["show_prompts"] = False
        await update.message.reply_text(
            format_script_message(script, show_prompts=False),
            parse_mode="Markdown"
        )
        return

    # SHOW PROMPTS
    if lower == "show prompts":
        context.user_data["show_prompts"] = True
        await update.message.reply_text(
            format_script_message(script, show_prompts=True),
            parse_mode="Markdown"
        )
        return

    # REWRITE SCENE N PROMPT
    if lower.startswith("rewrite scene") and "prompt" in lower:
        try:
            parts = lower.split()
            scene_num = int(parts[2])
            instruction = lower.split("prompt", 1)[1].strip() or "make it more unique and specific"
            scenes = script.get("scenes", [])
            if 1 <= scene_num <= len(scenes):
                msg = await update.message.reply_text(f"✍️ Rewriting Scene {scene_num} prompt…")
                new_scene = rewrite_scene_prompt(scenes[scene_num - 1], instruction, style)
                scenes[scene_num - 1] = new_scene
                script["scenes"] = scenes
                context.user_data["current_script"] = script
                await msg.delete()
                await update.message.reply_text(
                    f"✅ *Scene {scene_num} prompt updated:*\n\n"
                    f"📝 `{new_scene.get('minimax_prompt', '')[:150]}...`\n\n"
                    "Reply *`yes`* to generate or keep editing.",
                    parse_mode="Markdown"
                )
        except (IndexError, ValueError):
            await update.message.reply_text(
                "Usage: `rewrite scene 2 prompt more cinematic`",
                parse_mode="Markdown"
            )
        return

    # EDIT SCENE N PROMPT: [your text]
    if lower.startswith("edit scene") and "prompt:" in lower:
        try:
            parts   = lower.split("prompt:", 1)
            scene_num = int(parts[0].replace("edit scene", "").strip())
            new_prompt = text.split("prompt:", 1)[1].strip()
            scenes = script.get("scenes", [])
            if 1 <= scene_num <= len(scenes):
                scenes[scene_num - 1]["minimax_prompt"] = new_prompt
                script["scenes"] = scenes
                context.user_data["current_script"] = script
                await update.message.reply_text(
                    f"✅ *Scene {scene_num} prompt set to your text.*\n\n"
                    f"📝 `{new_prompt[:150]}`\n\n"
                    "Reply *`yes`* to generate.",
                    parse_mode="Markdown"
                )
        except (IndexError, ValueError):
            await update.message.reply_text(
                "Usage: `edit scene 3 prompt: girl running on beach at sunset`",
                parse_mode="Markdown"
            )
        return

    # REWRITE [instruction]
    if lower.startswith("rewrite"):
        instruction = lower.replace("rewrite", "").strip()
        msg = await update.message.reply_text("✍️ Rewriting…")
        try:
            new_script = rewrite_script(script, instruction)
            context.user_data["current_script"] = new_script
            await msg.delete()
            await update.message.reply_text(
                format_script_message(new_script, show_prompts=show_prompts),
                parse_mode="Markdown"
            )
        except Exception as e:
            await msg.edit_text(f"⚠️ {str(e)[:100]}")
        return

    # PART N — series
    if lower.startswith("part ") and lower.split()[1].isdigit():
        context.user_data["video_state"] = "idle"
        await handle_video_request(update, context)
        return

    # Voice style change at approval
    for vs in ["slow", "fast", "deep", "calm", "excited", "creepy"]:
        if vs in lower:
            context.user_data["voice_style"] = vs
            await update.message.reply_text(
                f"✅ Voice style set to *{vs}*.\n"
                "Reply *`yes`* to generate with this voice.",
                parse_mode="Markdown"
            )
            return

    await update.message.reply_text(
        "Reply *`yes`* to generate or *`rewrite`* for a new script.\n"
        "Say *`show prompts`* to see all Minimax prompts.",
        parse_mode="Markdown"
    )


async def handle_script_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    script = context.user_data.get("current_script")
    if not script:
        await update.message.reply_text("⚠️ No script. Start a new video request.")
        return

    scenes      = script.get("scenes", [])
    needs_voice = script.get("needs_voice", True)
    series_part = script.get("series_part", 1)

    if script.get("summary"):
        context.user_data["series_summary"] = script["summary"]
        context.user_data["video_topic"]    = script.get("title", "")

    context.user_data["video_state"]        = "selecting_clips"
    context.user_data["scenes"]             = scenes
    context.user_data["selected_clips"]     = {}
    context.user_data["current_scene_idx"]  = 0
    context.user_data["needs_voice"]        = needs_voice

    part_label  = f" Part {series_part}" if series_part > 1 else ""
    voice_note  = "Your cloned voice will be added." if needs_voice else "Visual only — no voiceover."

    await update.message.reply_text(
        f"🎬 *Generating{part_label}!*\n\n"
        f"{len(scenes)} scenes × {CLIPS_PER_SCENE} options each.\n"
        f"{voice_note}\n\n"
        f"_Takes ~{len(scenes) * 2}–{len(scenes) * 4} minutes…_",
        parse_mode="Markdown"
    )
    await _generate_scene_options(update, context, scenes[0], 1)


async def _generate_scene_options(update, context, scene, scene_number):
    status = await update.message.reply_text(
        f"⏳ Generating Scene {scene_number}… (~2 min)"
    )
    try:
        clip_paths = await generate_clip_options(
            scene=scene,
            scene_number=scene_number,
            num_options=CLIPS_PER_SCENE,
        )
        if not clip_paths:
            await status.edit_text(
                f"❌ Scene {scene_number} failed. Check Minimax API key and credits."
            )
            return

        context.user_data[f"scene_{scene_number}_options"] = clip_paths
        await status.delete()

        vo  = scene.get("voiceover", "")
        sfx = scene.get("sound_effects", "")
        caption = (
            f"🎬 *Scene {scene_number}* ({scene.get('start')}s–{scene.get('end')}s)\n"
            + (f"🎙️ _{vo[:80]}_\n" if vo else "")
            + (f"🔊 _{sfx[:60]}_\n" if sfx else "")
            + "\nChoose your favourite:"
        )
        await update.message.reply_text(caption, parse_mode="Markdown")

        for i, path in enumerate(clip_paths):
            with open(path, "rb") as f:
                await update.message.reply_video(
                    video=f,
                    caption=f"Option *{OPTION_LABELS[i]}*",
                    parse_mode="Markdown",
                )

        await update.message.reply_text(
            f"Reply *A*, *B* or *C* for Scene {scene_number}",
            parse_mode="Markdown"
        )
        context.user_data["current_scene_idx"] = scene_number - 1

    except Exception as e:
        await status.edit_text(f"❌ Scene {scene_number}: {str(e)[:100]}")


async def handle_clip_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice       = update.message.text.strip().upper()
    scene_idx    = context.user_data.get("current_scene_idx", 0)
    scenes       = context.user_data.get("scenes", [])
    scene_number = scene_idx + 1
    options      = context.user_data.get(f"scene_{scene_number}_options", [])
    label_map    = {OPTION_LABELS[i]: p for i, p in enumerate(options)}

    if choice not in label_map:
        await update.message.reply_text(
            f"Please reply *A*, *B* or *C* for Scene {scene_number}",
            parse_mode="Markdown"
        )
        return

    context.user_data["selected_clips"][scene_number] = label_map[choice]
    await update.message.reply_text(
        f"✅ Scene {scene_number} → *{choice}*", parse_mode="Markdown"
    )

    next_idx = scene_idx + 1
    if next_idx < len(scenes):
        context.user_data["current_scene_idx"] = next_idx
        await _generate_scene_options(update, context, scenes[next_idx], next_idx + 1)
    else:
        await _finalize_video(update, context)


async def _finalize_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    script         = context.user_data.get("current_script", {})
    scenes         = context.user_data.get("scenes", [])
    selected_clips = context.user_data.get("selected_clips", {})
    needs_voice    = context.user_data.get("needs_voice", True)
    voice_style    = context.user_data.get("voice_style", "natural")
    series_part    = script.get("series_part", 1)

    msg = await update.message.reply_text(
        "🎙️ Adding voice and merging…" if needs_voice else "🎬 Finalizing clips…"
    )

    complete_clips = []
    for i, scene in enumerate(scenes):
        scene_number = i + 1
        video_path   = selected_clips.get(scene_number, "")
        voiceover    = scene.get("voiceover", "")

        if not video_path or not os.path.exists(video_path):
            continue
        try:
            if needs_voice and voiceover:
                audio_path = await generate_voiceover(voiceover, scene_number, voice_style)
                if audio_path and os.path.exists(audio_path):
                    final_path = await merge_video_audio(video_path, audio_path, scene_number)
                else:
                    final_path = video_path
            else:
                final_path = video_path
            complete_clips.append((scene_number, final_path, voiceover))
        except Exception as e:
            print(f"[finalize] Scene {scene_number}: {e}")
            complete_clips.append((scene_number, video_path, voiceover))

    await msg.delete()

    part_label = f" Part {series_part}" if series_part > 1 else ""
    await update.message.reply_text(
        f"🎉 *{len(complete_clips)} clips ready{part_label}!*",
        parse_mode="Markdown"
    )

    for scene_number, path, vo in complete_clips:
        if os.path.exists(path):
            with open(path, "rb") as f:
                await update.message.reply_video(
                    video=f,
                    caption=(
                        f"✅ *Scene {scene_number}*"
                        + (f"\n_{vo[:80]}_" if vo else "")
                    ),
                    parse_mode="Markdown",
                )

    # Full script for captions
    script_lines = [f"📝 *Script{part_label} — for captions:*\n"]
    for scene in scenes:
        vo  = scene.get("voiceover", "")
        sfx = scene.get("sound_effects", "")
        script_lines.append(
            f"*Scene {scene.get('scene_number')}* "
            f"({scene.get('start')}s–{scene.get('end')}s)\n"
            + (f"{vo}\n" if vo else f"[{sfx}]\n")
        )
    await update.message.reply_text("\n".join(script_lines), parse_mode="Markdown")

    next_part = series_part + 1
    await update.message.reply_text(
        "✅ *Done!*\n\n"
        "1️⃣ Open *Ssemble*\n"
        "2️⃣ Drop clips in order\n"
        "3️⃣ Add captions from script\n"
        "4️⃣ Export and post 🚀\n\n"
        f"Say *`part {next_part}`* to continue the series.",
        parse_mode="Markdown"
    )

    context.user_data["video_state"] = "idle"
    context.user_data.pop("current_script", None)
    context.user_data.pop("selected_clips", None)
    context.user_data.pop("scenes", None)


async def handle_story_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user picking 1, 2, 3 or all from story options."""
    text    = update.message.text.strip().lower()
    options = context.user_data.get("story_options", [])
    niche   = context.user_data.get("video_niche", "")
    needs_voice = context.user_data.get("needs_voice", True)

    # Parse selection
    selected = []
    if text == "all":
        selected = list(range(len(options)))
    else:
        for part in text.split():
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    selected.append(idx)

    if not selected:
        await update.message.reply_text(
            "Reply *`1`*, *`2`*, *`3`*, *`1 2`* or *`all`* to choose.",
            parse_mode="Markdown"
        )
        return

    chosen = [options[i] for i in selected]

    # Queue multiple videos if more than one selected
    context.user_data["video_queue"]      = chosen[1:] if len(chosen) > 1 else []
    context.user_data["video_queue_idx"]  = 0
    context.user_data["video_state"]      = "awaiting_script_approval"

    # Write script for first selected story
    first = chosen[0]
    msg   = await update.message.reply_text(
        f"✍️ Writing script for *{first.get('title', '')}*…",
        parse_mode="Markdown"
    )

    if len(chosen) > 1:
        await update.message.reply_text(
            f"📋 *{len(chosen)} videos queued.* I will create them one by one after each is approved.",
            parse_mode="Markdown"
        )

    await _write_and_show_script(
        update, context,
        topic=first.get("title", ""),
        niche=niche,
        msg=msg,
        needs_voice=needs_voice,
        style=first.get("style", "ugc"),
    )
