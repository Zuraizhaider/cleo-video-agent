"""
services/claude_service.py
Handles all Claude API calls:
- Trending topic research
- Director POV script writing
- Script rewriting
- Smart clarification questions
"""
import anthropic
import json
import re
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _ask(system: str, user: str, max_tokens: int = 2000) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


def find_trending_topic() -> str:
    """Find a trending topic suitable for a YouTube short."""
    system = (
        "You are a YouTube Shorts content strategist. "
        "You know what is trending and what gets views. "
        "Return ONLY a single topic idea as a short phrase. No explanation."
    )
    user = (
        "Give me one trending YouTube Shorts topic right now that would get "
        "millions of views. It should be motivational, lifestyle, or educational. "
        "Return ONLY the topic as a short phrase like: "
        "'5 habits that changed my life' or 'morning routine that millionaires use'"
    )
    return _ask(system, user, max_tokens=100)


def write_director_script(
    topic: str,
    niche: str = "",
    style: str = "",
    extra_context: str = "",
) -> dict:
    """
    Write a full 60s YouTube Short script in director POV.
    Returns {title, scenes: [{start, end, visual, voiceover, director_note}]}
    """
    niche_line  = f"Niche/angle: {niche}." if niche else ""
    style_line  = f"Style: {style}." if style else ""
    extra_line  = f"Additional context: {extra_context}." if extra_context else ""

    system = (
        "You are an award-winning YouTube Shorts director and scriptwriter. "
        "You create viral, cinematic, emotionally engaging short-form content. "
        "You write scripts that feel human, not AI-generated. "
        "Every scene has specific visual direction, natural voiceover, and cinematic notes. "
        "Return ONLY a valid JSON object. No markdown, no explanation."
    )

    user = (
        f"Write a complete 60-second YouTube Shorts script for: '{topic}'\n"
        f"{niche_line} {style_line} {extra_line}\n\n"
        "Break it into exactly 6 scenes:\n"
        "Scene 1: 0s-5s (HOOK — grab attention immediately)\n"
        "Scene 2: 5s-15s (Setup/problem)\n"
        "Scene 3: 15s-25s (Development)\n"
        "Scene 4: 25s-40s (Main content/value)\n"
        "Scene 5: 40s-52s (Build up/climax)\n"
        "Scene 6: 52s-60s (CTA/resolution)\n\n"
        "For each scene provide:\n"
        "- start: start time in seconds\n"
        "- end: end time in seconds\n"
        "- visual: detailed cinematic visual description for AI video generation\n"
        "  (be very specific — lighting, camera angle, subject, movement, mood)\n"
        "- voiceover: natural spoken words for this scene (as if a real person speaking)\n"
        "- director_note: camera technique, emotion, pacing instruction\n"
        "- kling_prompt: optimized prompt for Hailuo AI video generation\n\n"
        "Make it feel 100% human-made. No robotic language. Natural flow.\n\n"
        "Return this exact JSON structure:\n"
        "{\n"
        '  "title": "video title",\n'
        '  "total_duration": 60,\n'
        '  "style": "cinematic/motivational/etc",\n'
        '  "scenes": [\n'
        "    {\n"
        '      "scene_number": 1,\n'
        '      "start": 0,\n'
        '      "end": 5,\n'
        '      "visual": "...",\n'
        '      "voiceover": "...",\n'
        '      "director_note": "...",\n'
        '      "kling_prompt": "..."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    raw = _ask(system, user, max_tokens=3000)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


def rewrite_script(
    original_script: dict,
    instruction: str = "",
) -> dict:
    """Completely rewrite the script with optional instruction."""
    topic = original_script.get("title", "the same topic")
    system = (
        "You are an award-winning YouTube Shorts director. "
        "Rewrite scripts to be completely fresh and different. "
        "Return ONLY valid JSON. No markdown."
    )
    instruction_line = f"Rewrite instruction: {instruction}" if instruction else "Completely reimagine the story."
    user = (
        f"Rewrite this YouTube Shorts script for '{topic}' completely differently.\n"
        f"{instruction_line}\n\n"
        "Use a completely different story angle, different scenes, different voiceover.\n"
        "Keep the same JSON structure as before with 6 scenes.\n"
        "Make it feel fresh and completely new.\n\n"
        f"Original title: {topic}\n"
        "Return the same JSON structure as a full new script."
    )
    raw = _ask(system, user, max_tokens=3000)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


def understand_request(message: str) -> dict:
    """
    Analyze user message and determine intent.
    Returns {
        intent: 'find_topic' | 'specific_topic' | 'scene_description',
        topic: str or None,
        niche: str or None,
        description: str or None,
        needs_clarification: bool,
        clarification_question: str or None
    }
    """
    system = (
        "You analyze YouTube Shorts video requests. "
        "Return ONLY valid JSON. No explanation."
    )
    user = (
        f"Analyze this video request: '{message}'\n\n"
        "Determine:\n"
        "1. intent: is it 'find_topic' (no topic given, find trending), "
        "'specific_topic' (clear topic given), or 'scene_description' "
        "(describing a character/scene/moment)\n"
        "2. topic: the topic if mentioned, else null\n"
        "3. niche: the niche/angle if mentioned (fitness, finance, travel etc), else null\n"
        "4. description: if scene_description, what they described\n"
        "5. needs_clarification: true only if scene_description "
        "(need to ask full short or single clip)\n"
        "6. clarification_question: the question to ask if needs_clarification is true\n\n"
        "Return JSON:\n"
        "{\n"
        '  "intent": "...",\n'
        '  "topic": "...",\n'
        '  "niche": "...",\n'
        '  "description": "...",\n'
        '  "needs_clarification": false,\n'
        '  "clarification_question": null\n'
        "}"
    )
    raw = _ask(system, user, max_tokens=500)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {
            "intent": "specific_topic",
            "topic": message,
            "niche": None,
            "description": None,
            "needs_clarification": False,
            "clarification_question": None,
        }


def format_script_message(script: dict) -> str:
    """Format script as a readable Telegram message."""
    lines = [
        f"🎬 *{script.get('title', 'Untitled')}*\n",
        f"_Style: {script.get('style', 'Cinematic')} · 60 seconds_\n",
        "─────────────────────────\n"
    ]
    for scene in script.get("scenes", []):
        n     = scene.get("scene_number", "?")
        start = scene.get("start", 0)
        end   = scene.get("end", 0)
        lines.append(
            f"*Scene {n}* ({start}s–{end}s)\n"
            f"🎥 _{scene.get('visual', ''[:80])}_\n"
            f"🎙️ \"{scene.get('voiceover', '')}\"\n"
            f"🎞️ {scene.get('director_note', '')}\n"
        )
    lines.append(
        "\n─────────────────────────\n"
        "Reply:\n"
        "• *`yes`* — generate videos\n"
        "• *`rewrite`* — new script\n"
        "• *`rewrite [instruction]`* — rewrite with your angle"
    )
    return "\n".join(lines)
