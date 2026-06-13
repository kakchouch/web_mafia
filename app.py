from __future__ import annotations
import json
import os
import random
import threading
import time

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

load_dotenv()
load_dotenv("api.secret")
load_dotenv("config.env")

import game.state as gs
import game.config as gcfg
from game.ai_director import NPC_PROFILES
from game.roles import ENGLISH_NAMES, ROLE_CONFIGS, ROLE_POOLS
from game.state import GameState, NPCMemory, Player
from game.phases import run_night

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def _build_game(player_name: str, role_choice: str, player_count: int, mode: str) -> GameState:
    state = GameState()
    state.mode = mode
    state.round = 1

    pool = ROLE_POOLS[player_count][:]
    random.shuffle(pool)

    if mode == "player" and role_choice in pool:
        pool.remove(role_choice)
        human_role = role_choice
    elif mode == "player":
        human_role = pool.pop(0)
    else:
        human_role = None

    names = random.sample(list(ENGLISH_NAMES.keys()), player_count - (1 if mode == "player" else 0))

    players: list[Player] = []

    if mode == "player":
        human = Player(
            id="human",
            name=player_name,
            role=human_role,
            team=ROLE_CONFIGS[human_role]["team"],
            is_alive=True,
            is_human=True,
        )
        players.append(human)
        state.human_id = "human"

    profile_pool = random.sample(list(NPC_PROFILES.keys()), len(NPC_PROFILES))
    for i, role in enumerate(pool):
        npc = Player(
            id=f"p{i+1}",
            name=names[i],
            role=role,
            team=ROLE_CONFIGS[role]["team"],
            is_alive=True,
            is_human=False,
            personality=profile_pool[i % len(profile_pool)],
        )
        players.append(npc)
        mem = NPCMemory()
        if role == "mafia":
            for other in players:
                if other.role == "mafia" and other.id != npc.id:
                    mem.suspicions[other.id] = -1.0
        state.npc_memories[npc.id] = mem

    random.shuffle(players)
    state.players = players

    mafia_ids = [p.id for p in players if p.role == "mafia"]
    for mid in mafia_ids:
        mem = state.npc_memories.get(mid)
        if mem:
            for other_id in mafia_ids:
                if other_id != mid:
                    mem.suspicions[other_id] = -1.0

    return state


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", config=gcfg.all_values())


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(gcfg.all_values())


@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.get_json() or {}
    gcfg.update(data)
    gcfg.save()
    from game import ai_director
    ai_director.reset_client()
    return jsonify({"ok": True, "config": gcfg.all_values()})


@app.route("/api/game/start", methods=["POST"])
def start_game():
    data = request.get_json() or {}
    player_name = str(data.get("player_name", "Player")).strip() or "Player"
    role_choice = data.get("role_choice", "random")
    player_count = max(
        int(gcfg.get("PLAYER_COUNT_MIN")),
        min(int(gcfg.get("PLAYER_COUNT_MAX")), int(data.get("player_count", gcfg.get("PLAYER_COUNT_DEFAULT")))),
    )
    mode = data.get("mode", "player")

    if role_choice not in ROLE_CONFIGS:
        role_choice = "random"

    with gs.GAME_LOCK:
        gs.GAME = _build_game(player_name, role_choice, player_count, mode)
        state = gs.GAME

    t = threading.Thread(target=_game_thread, args=(state,), daemon=True)
    t.start()

    human = state.get_human()
    male_idx = 0
    female_idx = 0
    players_out = []
    for p in state.players:
        entry = {"id": p.id, "name": p.name, "is_human": p.is_human}
        if not p.is_human:
            gender = ENGLISH_NAMES.get(p.name, "m")
            entry["gender"] = gender
            if gender == "f":
                entry["voice_index"] = female_idx
                female_idx += 1
            else:
                entry["voice_index"] = male_idx
                male_idx += 1
        players_out.append(entry)

    return jsonify({
        "ok": True,
        "mode": mode,
        "your_role": human.role if human else None,
        "your_role_label": ROLE_CONFIGS[human.role]["label"] if human else None,
        "your_role_emoji": ROLE_CONFIGS[human.role]["emoji"] if human else None,
        "your_name": human.name if human else None,
        "players": players_out,
    })


def _game_thread(state: GameState):
    try:
        run_night(state)
    except Exception as e:
        state.emit({"type": "error", "text": f"Internal error: {e}"})


@app.route("/api/game/state")
def game_state():
    state = gs.GAME
    if not state:
        return jsonify({"error": "no_game"})
    return jsonify({
        "phase": state.phase,
        "round": state.round,
        "mode": state.mode,
        "winner": state.winner,
        "players": [
            {"id": p.id, "name": p.name, "is_alive": p.is_alive, "is_human": p.is_human,
             "role": p.role if not p.is_alive else None}
            for p in state.players
        ],
        "pending_action": {
            "type": state.pending_action["type"],
            "targets": [{"id": t.id, "name": t.name} for t in state.pending_action["targets"]],
            "extra": state.pending_action["extra"],
        } if state.pending_action else None,
    })


@app.route("/api/action", methods=["POST"])
def take_action():
    state = gs.GAME
    if not state:
        return jsonify({"error": "no_game"}), 400

    data = request.get_json() or {}
    action_type = data.get("action_type", "")
    target_id = data.get("target_id", "")
    extra = data.get("extra", {})

    if action_type == "chat":
        if state.pending_action and state.pending_action["type"] == "chat":
            state.pending_action["result"] = {"target_id": None, "extra": {"message": data.get("message", "")}}
            state.pending_action["event"].set()
            return jsonify({"ok": True})

    ok = state.resolve_human_action(action_type, target_id, extra)
    if not ok:
        return jsonify({"error": "no_pending_action"}), 400
    return jsonify({"ok": True})


@app.route("/api/tts/ack", methods=["POST"])
def tts_ack():
    if gs.GAME:
        gs.GAME.tts_ack_event.set()
    return jsonify({"ok": True})


@app.route("/api/tts", methods=["POST"])
def tts_synthesize():
    from game.tts_engine import synthesize, is_ready
    if not is_ready():
        return jsonify({"error": "Kokoro models not found. Run: python download_models.py"}), 503

    data = request.get_json() or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return "", 204

    char_index = data.get("character_index")
    is_narrator = bool(data.get("is_narrator", False))
    speed_multiplier = float(data.get("speed_multiplier", 1.0))
    gender = str(data.get("gender", "m"))

    try:
        wav = synthesize(
            text,
            character_index=int(char_index) if char_index is not None else None,
            is_narrator=is_narrator,
            speed_multiplier=speed_multiplier,
            gender=gender,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return Response(wav, mimetype="audio/wav")


@app.route("/api/ollama/ps")
def ollama_ps():
    import subprocess
    try:
        r = subprocess.run(
            ["ollama", "ps"],
            capture_output=True, text=True, timeout=5,
        )
        return jsonify({"ok": True, "output": r.stdout.strip() or "(no model loaded)"})
    except FileNotFoundError:
        return jsonify({"ok": False, "output": "ollama not found in PATH"})
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)})


@app.route("/api/roles_info")
def roles_info():
    return jsonify({
        role: {
            "label": cfg["label"],
            "emoji": cfg["emoji"],
            "description": cfg["description"],
            "team": cfg["team"],
        }
        for role, cfg in ROLE_CONFIGS.items()
    })


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

@app.route("/api/events")
def sse_events():
    cursor = int(request.args.get("cursor", 0))
    mode = gs.GAME.mode if gs.GAME else "player"
    human = gs.GAME.get_human() if gs.GAME else None
    human_role = human.role if human else None
    human_team = human.team if human else None

    def event_stream():
        nonlocal cursor
        while True:
            state = gs.GAME
            if state is None:
                yield "data: {\"type\": \"no_game\"}\n\n"
                time.sleep(1)
                continue

            new_events = state.event_log[cursor:]
            for evt in new_events:
                cursor += 1
                if _should_send(evt, mode, human_role, human_team):
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

            time.sleep(0.4)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _should_send(evt: dict, mode: str, human_role: str | None, human_team: str | None) -> bool:
    visible = evt.get("visible", "all")

    if visible == "all":
        return True
    if mode == "spectator":
        return True
    if visible == "human":
        return True
    if visible == "mafia":
        return human_team == "mafia"
    if visible.startswith("spectator_or_role:"):
        role = visible.split(":")[1]
        return human_role == role
    if visible == "spectator":
        return False
    return True


if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)
