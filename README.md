# 🔫 Mafia — Python Web App

A browser-based Mafia game where a local LLM (via Ollama) plays all NPCs, narrates the game in real time, and speaks every line aloud through Kokoro TTS — no cloud API key required.

---

## Table of contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the game](#running-the-game)
- [Roles](#roles)
- [Role compositions](#role-compositions)
- [How a game plays out](#how-a-game-plays-out)
- [Game modes](#game-modes)
- [NPC personalities](#npc-personalities)
- [Technical architecture](#technical-architecture)
- [File structure](#file-structure)
- [Advanced configuration](#advanced-configuration)
  - [Recommended models (Ollama)](#recommended-models-ollama)

---

## Features

- **Full Mafia game** — dramatic narration, NPC dialogue, votes, and win conditions
- **Local AI** — Ollama runs the LLM on your machine; no API key, no cost
- **Multi-voice TTS** — Kokoro-ONNX gives each character a distinct voice, locally
- **Push-to-talk speech input** — hold the mic button to speak your dialogue (Chrome/Edge)
- **Two modes**:
  - **Player** — you play a role with information limited to what your role can see
  - **Spectator** — observe the full game with all secrets visible
- **6 roles**: Villager, Mafia, Sheriff, Doctor, Vigilante, Jester
- **4 to 12 players** with balanced compositions
- **NPC memory** — characters accumulate suspicions, track investigations, and remember past saves across rounds
- **10 distinct NPC personalities** — each name has a fixed personality that shapes LLM sampling and prompt behavior
- **Reactive interface** via Server-Sent Events (SSE) — no page reloads

---

## Prerequisites

- **Python 3.10+**
- **[Ollama](https://ollama.com)** installed and running locally
- A model pulled, e.g. `ollama pull qwen2.5:14b`
- A modern browser (Chrome or Edge recommended for push-to-talk; Firefox works without it)

---

## Installation

```bash
# Clone the repo
git clone https://github.com/your-username/mafia.git
cd mafia

# Create and activate a virtual environment (strongly recommended)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Download Kokoro TTS model files (~337 MB, one-time)
python download_models.py
```

Then set your model in [config.env](config.env):

```env
OLLAMA_MODEL=qwen2.5:14b
```

See [Recommended models](#recommended-models-ollama) for guidance on what to pick for your hardware.

**Optional — `api.secret`:** Copy [api.secret.example](api.secret.example) to `api.secret` if you need to set a custom `FLASK_SECRET_KEY` (recommended for network/LAN hosting):

```bash
cp api.secret.example api.secret
# then edit api.secret and set FLASK_SECRET_KEY to a long random string
```

---

## Running the game

```bash
python app.py
```

Then open **[http://localhost:5000](http://localhost:5000)** in your browser.

---

## Roles

### 🔫 Mafia — Mafia team
Each night, you and your partners secretly choose a town member to eliminate. During the day, blend in and deflect suspicion.

### 👤 Villager — Town team
No special power. Participate in discussions and vote during the day to root out the mafia.

### ⭐ Sheriff — Town team
Each night, investigate one player to learn whether they are **Mafia** or **Innocent**. Use your findings to guide the town — or keep them secret to protect yourself.

### 💉 Doctor — Town team
Each night, protect one player from being killed. You cannot protect the same person two nights in a row.

### 🎯 Vigilante — Town team
Once per game, shoot a player at night. If your target is innocent, you die of guilt immediately.

### 🃏 Jester — Jester team
Your **only** win condition is to be voted out by the town. Act suspicious without being so obvious that people realize what you're doing.

> The Jester appears **Innocent** to the Sheriff.

---

## Role compositions

| Players | 🔫 Mafia | ⭐ Sheriff | 💉 Doctor | 🎯 Vigilante | 🃏 Jester | 👤 Villager |
|:-------:|:--------:|:---------:|:---------:|:------------:|:---------:|:-----------:|
| 4       | 1        | 1         | —         | —            | —         | 2           |
| 5       | 1        | 1         | 1         | —            | —         | 2           |
| 6       | 2        | 1         | 1         | 1            | —         | 1           |
| 7       | 2        | 1         | 1         | 1            | —         | 2           |
| 8       | 2        | 1         | 1         | 1            | 1         | 2           |
| 9       | 2        | 1         | 1         | 1            | 1         | 3           |
| 10      | 3        | 1         | 1         | 1            | 1         | 3           |
| 11      | 3        | 1         | 1         | 1            | 1         | 4           |
| 12      | 3        | 1         | 1         | 1            | 1         | 5           |

---

## How a game plays out

### Setup screen
1. Enter your name (Player mode) or enable Spectator mode
2. Choose your preferred role, or leave it on Random
3. Set the number of players (4–12)
4. Click **Start game**

---

### 🌙 Night phase

Each role acts in order: Mafia → Doctor → Sheriff → Vigilante.

When it is **your** turn to act, an action panel appears at the bottom of the screen with target buttons. NPCs resolve their actions automatically.

---

### ☀️ Day phase — Discussion

The town discovers the night's casualties. NPCs speak in turn, accuse each other, defend themselves, and react to events. Their suspicions evolve across rounds based on the full game history.

**Your turn to speak**: a text field (with optional push-to-talk) appears. Write what you think — accusation, defence, bluff — or skip. NPCs react to what you say.

---

### 🗳 Vote phase

Every living player votes to eliminate a suspect. NPCs speak their vote aloud before casting it. A strict majority is required to eliminate someone; abstentions count against the target.

When a player is eliminated, their role is revealed to everyone.

---

### Win conditions

| Winner      | Condition |
|-------------|-----------|
| 🌅 Town     | All mafia members are eliminated |
| 🔫 Mafia    | Mafia equal or outnumber the remaining town |
| 🃏 Jester   | The Jester is voted out by the town |

---

## Game modes

### 🎭 Player mode
You participate actively. Your information is **strictly limited to your role**:
- A **Villager** does not see night actions
- A **Mafia** member sees the private deliberations of their partners
- The **Sheriff** sees the results of their own investigations
- The **Doctor** sees a confirmation when their save succeeds

### 👁 Spectator mode
You observe without playing. **Everything is visible**: mafia deliberations, sheriff results, doctor saves. Ideal for watching a fully AI-driven game unfold.

---

## NPC personalities

Each of the 20 NPC names has a fixed personality that is applied consistently across all games. Personality affects both the system prompt and the LLM sampling parameters (temperature, top_p, top_k).

| Personality  | Behaviour |
|--------------|-----------|
| calculating  | Cold, precise, cites facts, rarely changes target |
| aggressive   | Attacks directly, creates confrontations |
| anxious      | Hesitates, contradicts themselves, seeks reassurance |
| manipulative | Asks rhetorical questions, turns accusations back on accusers |
| naive        | Trusts easily, emotional reasoning, easily swayed |
| leader       | Takes charge, proposes votes, rallies others |
| discreet     | Speaks rarely but with precision |
| emotional    | Reacts strongly to deaths, empathy-driven arguments |
| logical      | Systematic reasoning, references past votes by index |
| performer    | Theatrical, dramatic, uses dark humour |

---

## Technical architecture

```
Browser (JS)  ←──SSE──  Flask (Python)  ──→  Ollama (local LLM)
     │                        │
  Kokoro TTS              threading
  (local)             (game runs in background thread)
```

### Key components

**Backend — Flask**
- No database: game state lives entirely in memory (`GameState`)
- A background thread runs the game; human actions unblock it via `threading.Event`
- SSE (`/api/events`) streams events to the browser in real time

**AI — Ollama**
- All LLM calls go to a local Ollama instance (OpenAI-compatible endpoint)
- Separate prompts for narration, NPC dialogue, NPC votes, and mafia night deliberation
- NPCs have persistent memory: suspicions, investigations (sheriff), saves (doctor), recent speech
- Per-personality sampling params shape each character's output variance

**TTS — Kokoro-ONNX**
- Runs entirely locally, no API key required
- Each character has a distinct voice assignment
- FIFO queue ensures lines don't overlap; narration interrupts ongoing speech

---

## File structure

```
mafia/
│
├── app.py              Flask entry point, API routes, SSE generator
├── config.env          All configuration (model, temperatures, timeouts, ports)
│
├── game/
│   ├── __init__.py
│   ├── state.py        GameState · Player · NPCMemory
│   ├── roles.py        Role definitions, compositions, NPC names & personalities
│   ├── ai_director.py  Ollama client: narration, NPC dialogue, votes, mafia deliberation
│   └── phases.py       Game state machine: run_night() and run_day()
│
├── static/
│   ├── css/style.css   Dark town theme (parchment, gold, blood red)
│   └── js/
│       ├── tts.js      Kokoro TTS bridge — distinct voices, FIFO queue
│       └── game.js     SSE consumer, action panels, player sidebar, push-to-talk STT
│
├── templates/
│   └── index.html      SPA: setup / game / game over / rules modal
│
├── models/                 Kokoro model files (gitignored — run download_models.py)
│   └── .gitkeep
├── api.secret.example      Template for api.secret (never commit api.secret itself)
├── download_models.py      One-time Kokoro model downloader
├── .gitignore
└── requirements.txt
```

---

## Advanced configuration

All settings live in [config.env](config.env). No restart required for most changes — restart Flask when changing the model or port.

### Recommended models (Ollama)

Model choice has a large impact on NPC believability — bigger models produce far more convincing dialogue, strategic reasoning, and personality expression. Set your model in [config.env](config.env):

```env
OLLAMA_MODEL=qwen2.5:14b
OLLAMA_CTX_SIZE=16384
```

#### By hardware tier

| Hardware | VRAM / RAM | Recommended model | Pull command | Notes |
|----------|------------|-------------------|--------------|-------|
| Entry GPU / iGPU | 4–6 GB VRAM | `llama3.2:3b` | `ollama pull llama3.2:3b` | Default config. Fast, passable dialogue |
| | | `qwen2.5:3b` | `ollama pull qwen2.5:3b` | Better instruction-following for the size |
| Mid-range GPU | 8–12 GB VRAM | `llama3.1:8b` | `ollama pull llama3.1:8b` | Good baseline quality |
| | | `qwen2.5:7b` | `ollama pull qwen2.5:7b` | Best roleplay and personality for its size |
| | | `mistral:7b` | `ollama pull mistral:7b` | Solid, fast |
| High-end GPU | 16–24 GB VRAM | `qwen2.5:14b` ⭐ | `ollama pull qwen2.5:14b` | Recommended sweet spot — noticeably more strategic NPC behaviour |
| | | `mistral-nemo:12b` | `ollama pull mistral-nemo:12b` | Good alternative |
| Enthusiast / multi-GPU | 32 GB+ VRAM | `qwen2.5:32b` | `ollama pull qwen2.5:32b` | Excellent reasoning and bluffing |
| | | `llama3.1:70b` | `ollama pull llama3.1:70b` | Best quality; requires quantization on a single GPU |
| CPU only | ≥ 32 GB RAM | `llama3.2:3b` | `ollama pull llama3.2:3b` | Only practical option — expect 30–90 s per NPC turn |

> **Context size (`OLLAMA_CTX_SIZE`):** The game feeds the full event history into every prompt. `16384` covers most games. Drop to `8192` if VRAM is tight; raise to `32768` for long games with many players. Higher context requires proportionally more VRAM.

> **Speed tip:** NPC turns are sequential, so response latency directly affects pacing. If turns feel slow, drop to a smaller model or reduce `OLLAMA_CTX_SIZE` before changing anything else.

---

### Localhost vs. network hosting

`FLASK_HOST` in [config.env](config.env) controls who can reach the server:

| Value | Access |
|-------|--------|
| `127.0.0.1` | Local machine only (default) |
| `0.0.0.0` | All network interfaces — other devices on your LAN can connect |

```env
# Single-player / local use (default)
FLASK_HOST=127.0.0.1

# LAN / hosted — lets other players connect from the same network
FLASK_HOST=0.0.0.0
```

When hosting on `0.0.0.0`, other players connect to your machine's local IP address (e.g. `http://192.168.1.42:5000`). Find it with `ipconfig` (Windows) or `ip a` (Linux/macOS).

> **Security note:** `0.0.0.0` exposes the server to your entire local network. Do not use it on untrusted networks (public Wi-Fi, etc.) without additional protection (firewall, reverse proxy, VPN).

### Change the port

In [config.env](config.env):
```env
FLASK_PORT=8080
```

### Disable debug mode (production)

In [config.env](config.env):
```env
FLASK_DEBUG=False
```

Always disable debug mode when the server is reachable by others — debug mode enables the Werkzeug interactive debugger, which allows arbitrary code execution.

### Add or rename NPC characters

In [game/roles.py](game/roles.py), edit the `ENGLISH_NAMES` dict and the `NAME_PERSONALITY` dict. Each name must map to one of the 10 personality keys.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `flask` | Web server, routes, SSE |
| `openai` | Ollama-compatible API client |
| `python-dotenv` | Loads `config.env` |
| `kokoro-onnx` | Local neural TTS engine |
| `soundfile` | Audio file I/O for Kokoro output |
