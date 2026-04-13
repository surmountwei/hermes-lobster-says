# 🦞 hermes-lobster-says

**LobsterSays** — your empathetic lobster companion, as a [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill.

Your lobster sends you personalized morning/evening messages, AI-generated stickers and wallpapers, and builds deep understanding of you over time.

## Install

```bash
hermes skills install jaredwei01/hermes-lobster-says
```

Then tell Hermes: **"I want to adopt a lobster"** (or "我想养一只共情虾").

## What it does

| Feature | Description |
|---------|-------------|
| 🌅 Morning & evening messages | Personalized daily check-ins based on your mood, weather, and recent context |
| 🔍 Discovery push | Daily curated insight tailored to your interests |
| 🎨 Stickers & wallpapers | AI-generated pixel art delivered on schedule |
| 🧠 Memory system | Three tiers: lightweight / smart / deep — your lobster learns who you are |
| 📸 Pixel studio | A live pixel-art studio for your lobster at [nixiashuo.com](https://nixiashuo.com) |

## How it works

```
Hermes Agent ←→ lobster-says skill (this repo)
                      ↕
              nixiashuo.com REST API
                      ↕
           LobsterSays Backend (shared)
```

The skill is a thin orchestration layer — all intelligence lives on the backend. This means:
- **Zero LLM cost** on the skill side
- **Shared backend** with the [OpenClaw version](https://clawhub.ai/jaredwei01/lobster-says)
- Your lobster's personality, memory, and art are fully portable

## Files

```
├── SKILL.md                    # agentskills.io spec — Hermes reads this
├── README.md
├── LICENSE
└── scripts/
    ├── init_lobster.py         # Create or reuse a lobster + save config
    ├── push_message.py         # Generate & deliver a scheduled message
    ├── register_crons.py       # Batch register/rebuild Hermes cron jobs
    ├── digest_transcript.py    # Digest recent chat history into memory
    ├── ingest_memory.py        # Inject extracted info into lobster memory
    ├── get_status.py           # Query lobster status
    ├── get_memory.py           # View lobster memory
    ├── get_studio_link.py      # Get a short-lived studio link
    ├── generate_message.py     # Manually trigger message generation
    └── update_config.py        # Update push schedule / memory mode
```

## Requirements

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) v0.8+
- Python 3.10+
- Network access to `nixiashuo.com`

## Also available for OpenClaw

If you use [OpenClaw](https://openclaw.ai) instead of Hermes:

```
clawhub install lobster-says
```

## License

MIT
