"""
services/claude_service.py
All Claude API calls — script writing, topic research, style detection.
"""
import json
from config import ANTHROPIC_API_KEY

_client = None

def _get_client():
    global _client
    if not ANTHROPIC_API_KEY:
        raise Exception(
            "Script writing needs your Anthropic API key.\n"
            "Add ANTHROPIC_API_KEY in Railway Variables."
        )
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _ask(system: str, user: str, max_tokens: int = 2000) -> str:
    response = _get_client().messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


def find_trending_topic() -> str:
    system = (
        "You are a YouTube Shorts content strategist. "
        "Return ONLY a single trending topic as a short phrase. No explanation."
    )
    user = (
        "Give me one trending YouTube Shorts topic right now that would get "
        "millions of views. Motivational, lifestyle, or educational. "
        "Return ONLY the topic phrase."
    )
    return _ask(system, user, max_tokens=100)


def detect_style(topic: str, user_message: str) -> str:
    """
    Auto detect best video style from topic and message.
    Returns one of: ugc, cinematic, animals, horror, animated, fantasy
    """
    system = "You detect the best video style. Return ONLY one word."
    user = (
        f"Topic: '{topic}'\nUser message: '{user_message}'\n\n"
        "What is the best video style?\n"
        "Options:\n"
        "- ugc (real person, authentic, daily life, fitness, beauty, lifestyle)\n"
        "- cinematic (epic, dramatic, nature, travel, motivational)\n"
        "- animals (pets, funny animals, parrot, dog, cat)\n"
        "- horror (scary, creepy, dark, thriller, ghost)\n"
        "- animated (cartoon, anime, illustrated, colorful)\n"
        "- fantasy (dragons, magic, sci-fi, space, adventure)\n\n"
        "If user specified a style in their message, use that.\n"
        "Otherwise pick the best match.\n"
        "Return ONLY one word from the options above."
    )
    result = _ask(system, user, max_tokens=10).strip().lower()
    valid = ["ugc", "cinematic", "animals", "horror", "animated", "fantasy"]
    return result if result in valid else "ugc"


def _build_minimax_prompt(visual: str, style: str, scene_number: int) -> str:
    """
    Build a high quality Minimax prompt based on style.
    This is what gets sent to Minimax — never shown to user unless requested.
    """
    style_prefixes = {
        "ugc": (
            "Vertical smartphone footage, slightly handheld shaky, "
            "authentic candid real person, natural lighting, "
            "filmed on iPhone, no professional equipment, genuine moment, "
        ),
        "cinematic": (
            "Ultra cinematic 4K vertical video, dramatic professional lighting, "
            "film grain, shallow depth of field, movie quality, "
            "professional camera movement, "
        ),
        "animals": (
            "Close up animal footage, bright natural colors, "
            "funny expressive animal face, clear sharp focus, "
            "natural environment, charming and entertaining, "
        ),
        "horror": (
            "Dark atmospheric vertical video, deep shadows, "
            "eerie lighting, suspenseful mood, slight film grain, "
            "unsettling atmosphere, thriller quality, "
        ),
        "animated": (
            "Vibrant animated style, colorful illustration, "
            "smooth animation, expressive characters, "
            "high quality render, engaging visual style, "
        ),
        "fantasy": (
            "Epic fantasy vertical video, magical atmosphere, "
            "stunning visual effects, dramatic lighting, "
            "high budget production quality, immersive world, "
        ),
    }
    prefix = style_prefixes.get(style, style_prefixes["ugc"])
    return f"{prefix}{visual}, vertical 9:16 format, high quality"


def understand_request(message: str) -> dict:
    """Analyze user message and determine video intent."""
    system = "You analyze video requests. Return ONLY valid JSON."
    user = (
        f"Analyze this video request: '{message}'\n\n"
        "Return JSON:\n"
        "{\n"
        '  "intent": "find_topic|specific_topic|scene_description|personal_video|funny_animals",\n'
        '  "topic": null,\n'
        '  "niche": null,\n'
        '  "description": null,\n'
        '  "style": null,\n'
        '  "is_series": false,\n'
        '  "series_part": 1,\n'
        '  "needs_clarification": false,\n'
        '  "clarification_question": null,\n'
        '  "needs_voice": true,\n'
        '  "voice_style": null\n'
        "}\n\n"
        "intent options:\n"
        "- find_topic: no topic given, should search trending\n"
        "- specific_topic: clear topic given\n"
        "- scene_description: describing a character or scene\n"
        "- personal_video: personal non-YouTube video\n"
        "- funny_animals: pets or funny animal content\n\n"
        "style: ugc/cinematic/animals/horror/animated/fantasy or null if not mentioned\n"
        "needs_voice: false only for funny animals or pure scenic personal videos\n"
        "voice_style: slow/fast/deep/calm/creepy/excited or null if not mentioned\n"
        "is_series: true if they mention part 2/3, series, or continue\n"
        "needs_clarification: true only for scene_description"
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
            "style": None,
            "is_series": False,
            "series_part": 1,
            "needs_clarification": False,
            "clarification_question": None,
            "needs_voice": True,
            "voice_style": None,
        }


def write_director_script(
    topic: str,
    niche: str = "",
    style: str = "",
    needs_voice: bool = True,
    series_part: int = 1,
    previous_summary: str = "",
    voice_style: str = "",
) -> dict:
    """Write full 60s script with visible prompts per scene."""

    # Auto detect style if not provided
    if not style:
        style = detect_style(topic, topic)

    niche_line   = f"Category/niche: {niche}." if niche else ""
    series_line  = (
        f"This is Part {series_part}. Previous: {previous_summary}. Continue naturally."
        if series_part > 1 and previous_summary else ""
    )
    voice_note = (
        "Include natural voiceover for each scene."
        if needs_voice
        else "NO voiceover — visual and ambient sounds only."
    )
    voice_style_note = (
        f"Voice delivery style: {voice_style}."
        if voice_style else ""
    )

    system = (
        "You are an award-winning YouTube Shorts director. "
        "You write viral scripts that feel 100% human. "
        "You write highly specific Minimax AI video prompts that generate "
        "unique high quality footage — never generic or cheap looking. "
        "Return ONLY valid JSON."
    )

    user = (
        f"Write a 60-second YouTube Shorts script.\n"
        f"Topic: '{topic}'\n"
        f"Visual style: {style}\n"
        f"{niche_line} {series_line} {voice_note} {voice_style_note}\n\n"
        "6 scenes:\n"
        "Scene 1: 0s-5s (HOOK)\n"
        "Scene 2: 5s-15s (Setup)\n"
        "Scene 3: 15s-25s (Development)\n"
        "Scene 4: 25s-40s (Main content)\n"
        "Scene 5: 40s-52s (Build up)\n"
        "Scene 6: 52s-60s (CTA/ending)\n\n"
        "For each scene provide:\n"
        "- scene_number, start, end\n"
        "- visual: what happens in this scene (plain description)\n"
        "- voiceover: natural spoken words (or sound description if no voice)\n"
        "- director_note: camera and emotion instruction\n"
        "- minimax_prompt: highly specific, detailed prompt for Minimax Hailuo AI.\n"
        "  Must be unique, specific, avoid generic AI look.\n"
        f"  Style prefix to use: {style}\n"
        "  Include: shot type, lighting, subject details, movement, mood, atmosphere\n"
        "- sound_effects: ambient sounds or music mood\n\n"
        "Return JSON:\n"
        "{\n"
        '  "title": "video title",\n'
        f'  "style": "{style}",\n'
        f'  "series_part": {series_part},\n'
        f'  "needs_voice": {str(needs_voice).lower()},\n'
        '  "voice_style": "' + (voice_style or "natural") + '",\n'
        '  "summary": "2 sentence summary for series continuity",\n'
        '  "scenes": [\n'
        "    {\n"
        '      "scene_number": 1,\n'
        '      "start": 0, "end": 5,\n'
        '      "visual": "...",\n'
        '      "voiceover": "...",\n'
        '      "director_note": "...",\n'
        '      "minimax_prompt": "...",\n'
        '      "sound_effects": "..."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    raw = _ask(system, user, max_tokens=3500)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


def rewrite_scene_prompt(scene: dict, instruction: str, style: str) -> dict:
    """Rewrite the minimax_prompt for a single scene."""
    system = (
        "You are a Minimax AI video prompt expert. "
        "Rewrite prompts to be highly specific and unique. "
        "Return ONLY valid JSON with same structure as input scene."
    )
    user = (
        f"Rewrite the minimax_prompt for this scene.\n"
        f"Instruction: {instruction}\n"
        f"Style: {style}\n"
        f"Current scene: {json.dumps(scene)}\n\n"
        "Keep all other fields the same. Only improve the minimax_prompt.\n"
        "Make it highly specific, unique, avoid generic AI look.\n"
        "Return the complete scene JSON with updated minimax_prompt."
    )
    raw = _ask(system, user, max_tokens=800)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(raw)
    except Exception:
        return scene


def rewrite_script(original_script: dict, instruction: str = "") -> dict:
    """Completely rewrite the script."""
    topic      = original_script.get("title", "the same topic")
    style      = original_script.get("style", "ugc")
    needs_voice = original_script.get("needs_voice", True)
    system = (
        "You are an award-winning YouTube Shorts director. "
        "Rewrite scripts completely fresh. Return ONLY valid JSON."
    )
    user = (
        f"Completely rewrite this script for '{topic}'.\n"
        f"Style: {style}\n"
        f"Instruction: {instruction if instruction else 'Completely reimagine it.'}\n"
        f"needs_voice: {needs_voice}\n"
        "Different story, different scenes, different voiceover.\n"
        "Same JSON structure with 6 scenes including minimax_prompt per scene."
    )
    raw = _ask(system, user, max_tokens=3500)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


def format_script_message(script: dict, show_prompts: bool = True) -> str:
    """Format script as readable Telegram message with prompts visible."""
    part       = script.get("series_part", 1)
    title      = script.get("title", "Untitled")
    style      = script.get("style", "ugc").upper()
    has_voice  = script.get("needs_voice", True)
    voice_style = script.get("voice_style", "natural")

    part_label   = f" — Part {part}" if part > 1 else ""
    voice_label  = f"🎙️ Voice: {voice_style}" if has_voice else "🔇 No voiceover"

    lines = [
        f"🎬 *{title}{part_label}*",
        f"_{style} style · 60s · {voice_label}_\n",
        "─────────────────────────",
    ]

    for scene in script.get("scenes", []):
        n      = scene.get("scene_number", "?")
        start  = scene.get("start", 0)
        end    = scene.get("end", 0)
        visual = scene.get("visual", "")
        vo     = scene.get("voiceover", "")
        note   = scene.get("director_note", "")
        prompt = scene.get("minimax_prompt", "")
        sfx    = scene.get("sound_effects", "")

        lines.append(f"\n*Scene {n}* ({start}s–{end}s)")
        lines.append(f"🎥 {visual}")
        if vo and has_voice:
            lines.append(f"🎙️ \"{vo}\"")
        if sfx:
            lines.append(f"🔊 _{sfx}_")
        lines.append(f"🎞️ _{note}_")
        if show_prompts and prompt:
            lines.append(f"📝 *Prompt:* `{prompt[:120]}...`")

    lines.append("\n─────────────────────────")
    lines.append(
        "Reply:\n"
        "• *`yes`* — generate all scenes\n"
        "• *`rewrite`* — new script\n"
        "• *`rewrite scene 2 prompt`* — rewrite one scene prompt\n"
        "• *`edit scene 3 prompt: [your text]`* — use your own prompt\n"
        "• *`hide prompts`* — hide prompts from view\n"
        "• *`show prompts`* — show prompts again"
    )
    return "\n".join(lines)
