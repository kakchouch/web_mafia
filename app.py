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

import game.state as gs
from game.roles import FRENCH_NAMES, ROLE_CONFIGS, ROLE_POOLS
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

    # Respecter la préférence de rôle si possible
    if mode == "player" and role_choice in pool:
        pool.remove(role_choice)
        human_role = role_choice
    elif mode == "player":
        human_role = pool.pop(0)
    else:
        human_role = None

    # Noms français distincts
    names = random.sample(FRENCH_NAMES, player_count - (1 if mode == "player" else 0))

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

    for i, role in enumerate(pool):
        npc = Player(
            id=f"p{i+1}",
            name=names[i],
            role=role,
            team=ROLE_CONFIGS[role]["team"],
            is_alive=True,
            is_human=False,
        )
        players.append(npc)
        mem = NPCMemory()
        # Loups se connaissent entre eux
        if role == "loup-garou":
            for other in players:
                if other.role == "loup-garou" and other.id != npc.id:
                    mem.suspicions[other.id] = -1.0
        state.npc_memories[npc.id] = mem

    random.shuffle(players)
    state.players = players

    # Les loups se connaissent entre eux (deuxième passe complète)
    wolf_ids = [p.id for p in players if p.role == "loup-garou"]
    for wid in wolf_ids:
        mem = state.npc_memories.get(wid)
        if mem:
            for other_id in wolf_ids:
                if other_id != wid:
                    mem.suspicions[other_id] = -1.0

    return state


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/game/start", methods=["POST"])
def start_game():
    data = request.get_json() or {}
    player_name = str(data.get("player_name", "Joueur")).strip() or "Joueur"
    role_choice = data.get("role_choice", "random")
    player_count = max(4, min(8, int(data.get("player_count", 6))))
    mode = data.get("mode", "player")

    if role_choice not in ROLE_CONFIGS:
        role_choice = "random"

    with gs.GAME_LOCK:
        gs.GAME = _build_game(player_name, role_choice, player_count, mode)
        state = gs.GAME

    # Démarrer le thread de jeu
    t = threading.Thread(target=_game_thread, args=(state,), daemon=True)
    t.start()

    human = state.get_human()
    return jsonify({
        "ok": True,
        "mode": mode,
        "your_role": human.role if human else None,
        "your_role_label": ROLE_CONFIGS[human.role]["label"] if human else None,
        "your_role_emoji": ROLE_CONFIGS[human.role]["emoji"] if human else None,
        "your_name": human.name if human else None,
        "players": [
            {"id": p.id, "name": p.name, "is_human": p.is_human}
            for p in state.players
        ],
    })


def _game_thread(state: GameState):
    try:
        run_night(state)
    except Exception as e:
        state.emit({"type": "error", "text": f"Erreur interne : {e}"})


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
             "role": p.role if not p.is_alive else None}  # révèle rôle seulement si mort
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

    # Action spéciale : message de discussion (pas de target)
    if action_type == "chat":
        if state.pending_action and state.pending_action["type"] == "chat":
            state.pending_action["result"] = {"target_id": None, "extra": {"message": data.get("message", "")}}
            state.pending_action["event"].set()
            return jsonify({"ok": True})

    ok = state.resolve_human_action(action_type, target_id, extra)
    if not ok:
        return jsonify({"error": "no_pending_action"}), 400
    return jsonify({"ok": True})


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
        return True  # le spectateur voit tout
    if visible == "human":
        return True
    if visible == "wolves":
        return human_team == "loups"
    if visible.startswith("spectator_or_role:"):
        role = visible.split(":")[1]
        return human_role == role
    if visible == "spectator":
        return False  # mode joueur ne voit pas ces événements
    return True


if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)
