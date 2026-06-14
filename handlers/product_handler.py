"""
handlers/product_handler.py
Product ad / hypermotion flow:
- Photo sent: Cleo analyzes, writes best prompt, confirm, generate
- Photo + caption: uses your prompt or refines it, confirm, generate  
- Text only with ad/product/demo: text-to-video demo, confirm, generate
"""
import os
import base64
import json
from telegram import Update
from telegram.ext import ContextTypes
from services.image_to_video_service import generate_product_ad
from config import ANTHROPIC_API_KEY


def _get_client():
    if not ANTHROPIC_API_KEY:
        raise Exception(
            "Product ad needs your Anthropic API key. "
            "Add ANTHROPIC_API_KEY in Railway Variables."
        )
    import anthropic
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def analyze_and_generate_prompt(
    image_path=None,
    user_caption="",
    product_description="",
) -> dict:
    client = _get_client()
    import anthropic

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        ext  = image_path.split(".")[-1].lower()
        mime = "image/jpeg" if ext in ["jpg","jpeg"] else f"image/{ext}"

        has_user_prompt = bool(user_caption and "improve" not in user_caption.lower())

        if has_user_prompt:
            task = (
                f"The user wants this motion: '{user_caption}'\n\n"
                "Enhance into a highly specific Minimax video prompt. "
                "Keep user's core idea but add precise camera terminology, "
                "lighting details, and commercial aesthetic language.\n\n"
                "Return JSON: {\"prompt\": \"...\", \"product_type\": \"...\", \"style_notes\": \"...\"}"
            )
        else:
            task = (
                "Analyze this product image. Identify what it is. "
                "Write the perfect hypermotion commercial prompt for Minimax Hailuo AI.\n\n"
                "Include: specific camera movement, lighting, background, motion speed, "
                "product-specific details, commercial aesthetic.\n\n"
                "Return JSON: {\"prompt\": \"...\", \"product_type\": \"...\", \"style_notes\": \"...\"}"
            )

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=800,
            system="You are a professional AI video director for hypermotion product ads. Return ONLY valid JSON.",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": image_data}},
                    {"type": "text", "text": task}
                ]
            }]
        )
    else:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            system="You are a professional AI video director for hypermotion product ads. Return ONLY valid JSON.",
            messages=[{
                "role": "user",
                "content": (
                    f"Create a hypermotion product ad prompt for: '{product_description}'\n\n"
                    "No real photo — describe the product visually AND write motion directions.\n"
                    "Make it cinematic and high-budget.\n\n"
                    "Return JSON: {\"prompt\": \"...\", \"product_type\": \"...\", \"style_notes\": \"...\"}"
                )
            }]
        )

    raw = response.content[0].text.strip()
    raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"prompt": raw, "product_type": "product", "style_notes": "commercial style"}


async def handle_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo   = update.message.photo[-1]
    caption = (update.message.caption or "").strip()
    msg     = await update.message.reply_text("Analyzing your product...")

    file = await context.bot.get_file(photo.file_id)
    image_path = "/tmp/product_input.jpg"
    await file.download_to_drive(image_path)

    context.user_data["product_image_path"] = image_path
    context.user_data["product_caption"]    = caption

    try:
        result       = await analyze_and_generate_prompt(image_path=image_path, user_caption=caption)
        prompt       = result.get("prompt", "")
        product_type = result.get("product_type", "product")
        style_notes  = result.get("style_notes", "")

        context.user_data["product_prompt"] = prompt
        context.user_data["product_type"]   = product_type
        context.user_data["video_state"]    = "awaiting_product_approval"

        note = "I used your prompt and enhanced it." if caption else "I analyzed your product automatically."

        await msg.edit_text(
            "Product: " + product_type + "\n" +
            note + "\n\n" +
            "Prompt:\n" + prompt + "\n\n" +
            "Reply:\n"
            "yes - generate the ad\n"
            "rewrite: [instruction] - adjust\n"
            "rewrite - redo completely"
        )
    except Exception as e:
        await msg.edit_text("Analysis failed: " + str(e)[:150])


async def handle_demo_ad_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    msg  = await update.message.reply_text("Creating demo ad prompt...")

    try:
        result       = await analyze_and_generate_prompt(product_description=text)
        prompt       = result.get("prompt", "")
        product_type = result.get("product_type", "product")

        context.user_data["product_prompt"]     = prompt
        context.user_data["product_type"]       = product_type
        context.user_data["product_image_path"] = None
        context.user_data["video_state"]        = "awaiting_product_approval"

        await msg.edit_text(
            "Demo product: " + product_type + "\n\n" +
            "Prompt:\n" + prompt + "\n\n" +
            "Reply:\n"
            "yes - generate demo ad\n"
            "rewrite: [instruction] - adjust\n"
            "rewrite - redo completely"
        )
    except Exception as e:
        await msg.edit_text("Failed: " + str(e)[:150])


async def handle_product_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text         = update.message.text.strip().lower()
    prompt       = context.user_data.get("product_prompt", "")
    image_path   = context.user_data.get("product_image_path")
    product_type = context.user_data.get("product_type", "product")

    if text.startswith("rewrite"):
        instruction = text.replace("rewrite", "").replace(":", "").strip()
        msg = await update.message.reply_text("Rewriting prompt...")
        try:
            result     = await analyze_and_generate_prompt(
                image_path=image_path,
                user_caption=instruction,
                product_description=instruction or product_type,
            )
            new_prompt = result.get("prompt", "")
            context.user_data["product_prompt"] = new_prompt
            await msg.edit_text(
                "Updated prompt:\n" + new_prompt + "\n\n"
                "Reply yes to generate or rewrite again."
            )
        except Exception as e:
            await msg.edit_text("Rewrite failed: " + str(e)[:100])
        return

    if any(w in text for w in ["yes", "go", "ok", "generate", "do it"]):
        msg = await update.message.reply_text(
            "Generating " + product_type + " ad... (~4 minutes)"
        )
        try:
            video_path = await generate_product_ad(prompt=prompt, image_path=image_path)
            await msg.delete()
            with open(video_path, "rb") as f:
                await update.message.reply_video(
                    video=f,
                    caption=(
                        product_type.title() + " ad ready!\n\n"
                        "Send another photo or say 'try again' for a variation."
                    )
                )
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
            if os.path.exists(video_path):
                os.remove(video_path)
            context.user_data["video_state"] = "idle"
            context.user_data.pop("product_prompt", None)
            context.user_data.pop("product_image_path", None)
        except Exception as e:
            await msg.edit_text("Generation failed: " + str(e)[:150])
        return

    if "try again" in text or "another" in text:
        msg = await update.message.reply_text("Generating another variation...")
        try:
            video_path = await generate_product_ad(prompt=prompt, image_path=image_path)
            await msg.delete()
            with open(video_path, "rb") as f:
                await update.message.reply_video(video=f, caption="New variation!")
            context.user_data["video_state"] = "idle"
        except Exception as e:
            await msg.edit_text("Failed: " + str(e)[:150])
        return

    await update.message.reply_text(
        "Reply yes to generate or rewrite: [instruction] to adjust."
    )


def is_product_ad_request(text: str) -> bool:
    text_lower = text.lower()
    ad_words   = ["ad", "ads", "advertisement", "commercial", "product", "demo",
                  "promo", "promotion", "hypermotion", "hyper motion", "motion ad",
                  "3d ad", "animate product", "product video", "brand video",
                  "showcase", "campaign", "portfolio"]
    short_words = ["story", "short", "youtube", "channel", "make a video on",
                   "video about", "create a video on", "find a story", "series"]
    has_ad    = any(w in text_lower for w in ad_words)
    has_short = any(w in text_lower for w in short_words)
    return has_ad and not has_short
