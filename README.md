# 🎬 Cleo — Video Agent

Create full cinematic YouTube Shorts from your phone via Telegram.
Just tell Cleo what you want — it writes the script, generates videos,
clones your voice, merges everything, and sends you complete clips ready for Ssemble.

---

## What you need

| Service | Cost | What for |
|---------|------|---------|
| Anthropic API | ~$0.01/video | Script writing |
| Minimax Hailuo API | ~$1/video | AI video generation |
| Telegram Bot | Free | Your interface |
| Railway | Free tier or ~$5/mo | 24/7 hosting |
| gTTS / OpenVoice | Free | Voice cloning |
| FFmpeg | Free | Video + audio merge |
| Ssemble | Free | Final editing + captions |

---

## Railway Environment Variables

```
TELEGRAM_BOT_TOKEN     your_telegram_bot_token
ANTHROPIC_API_KEY      sk-ant-...
MINIMAX_API_KEY        your_minimax_api_key
MINIMAX_GROUP_ID       your_minimax_group_id
BOT_NAME               Cleo
CLIPS_PER_SCENE        3
```

---

## How to get Minimax API key

1. Go to platform.minimaxi.com
2. Sign up / log in
3. Go to API Keys section
4. Create new key — copy it
5. Also copy your Group ID from account settings

---

## How to Use

**Find trending topic automatically:**
```
Hey Cleo find a perfect story lets create a video
```

**Specific topic:**
```
Hey Cleo make a video on morning routines for fitness
```

**Describe a scene:**
```
Hey Cleo make a video of a girl jogging at sunrise feeling motivated
```

**Setup voice clone:**
Send a voice message of 20-30 seconds to the bot

**During script review:**
- `yes` — approve script and generate videos
- `rewrite` — completely new script
- `rewrite shorter` — rewrite with instruction

**During scene selection:**
- Reply `A`, `B`, or `C` to choose each scene clip

---

## Full Flow

```
1. You send video request naturally
2. Bot understands and asks ONE clarifying question if needed
3. Claude writes 60s director script (6 scenes)
4. Bot sends you full script for approval
5. You say yes (or rewrite)
6. Bot generates 3 video options per scene via Minimax Hailuo
7. You pick A/B/C for each scene
8. Bot generates your cloned voice per scene
9. Bot merges video + voice with FFmpeg
10. Bot sends you 6 complete clips + full script
11. You open Ssemble, drop clips, add captions, export, post!
```

---

## Anti-AI Detection for YouTube Monetization

- Director POV prompting makes motion natural and human-feeling
- 3 different variations per scene — no repeated patterns
- Your real cloned voice — not synthetic TTS
- Human editing layer in Ssemble
- Manual captions — not burned in by AI
