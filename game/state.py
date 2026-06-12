from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Player:
    id: str
    name: str
    role: str          # loup-garou | villageois | voyante | sorciere | chasseur | cupidon
    team: str          # village | loups
    is_alive: bool = True
    is_human: bool = False
    witch_heal_used: bool = False
    witch_kill_used: bool = False
    lover_id: Optional[str] = None


@dataclass
class NPCMemory:
    suspicions: dict = field(default_factory=dict)   # player_id -> float 0.0-1.0
    known_role: Optional[str] = None                  # voyante PNJ seulement
    recent_speech: list = field(default_factory=list) # 3 dernières répliques


class GameState:
    def __init__(self):
        self.phase: str = "setup"
        self.round: int = 0
        self.mode: str = "player"        # player | spectator
        self.players: list[Player] = []
        self.human_id: Optional[str] = None
        self.night_actions: dict = {}
        self.pending_action: Optional[dict] = None
        self.votes: dict = {}
        self.event_log: list[dict] = []
        self.winner: Optional[str] = None
        self.npc_memories: dict[str, NPCMemory] = {}
        self._lock = threading.Lock()

    def emit(self, event: dict):
        with self._lock:
            self.event_log.append(event)

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.is_alive]

    def alive_wolves(self) -> list[Player]:
        return [p for p in self.players if p.is_alive and p.team == "loups"]

    def alive_village(self) -> list[Player]:
        return [p for p in self.players if p.is_alive and p.team == "village"]

    def get_player(self, player_id: str) -> Optional[Player]:
        return next((p for p in self.players if p.id == player_id), None)

    def get_human(self) -> Optional[Player]:
        if self.human_id:
            return self.get_player(self.human_id)
        return None

    def check_win(self) -> Optional[str]:
        wolves = self.alive_wolves()
        village = self.alive_village()
        if not wolves:
            return "village"
        if len(wolves) >= len(village):
            return "loups"
        # Condition amoureux : si exactement 2 joueurs vivants et ce sont les amoureux
        alive = self.alive_players()
        if len(alive) == 2 and alive[0].lover_id == alive[1].id:
            return "amoureux"
        return None

    def await_human_action(self, action_type: str, targets: list, extra: dict = None) -> Optional[dict]:
        evt = threading.Event()
        self.pending_action = {
            "type": action_type,
            "targets": targets,
            "extra": extra or {},
            "event": evt,
            "result": None,
        }
        self.emit({
            "type": "awaiting_action",
            "action": {
                "type": action_type,
                "targets": [{"id": t.id, "name": t.name} for t in targets],
                "extra": extra or {},
            },
        })
        evt.wait(timeout=300)
        result = self.pending_action.get("result")
        self.pending_action = None
        return result

    def resolve_human_action(self, action_type: str, target_id: str, extra: dict = None):
        with self._lock:
            if self.pending_action and self.pending_action["type"] == action_type:
                self.pending_action["result"] = {"target_id": target_id, "extra": extra or {}}
                self.pending_action["event"].set()
                return True
        return False


GAME: Optional[GameState] = None
GAME_LOCK = threading.Lock()
