from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Player:
    id: str
    name: str
    role: str          # mafia | villager | sheriff | doctor | vigilante | jester
    team: str          # town | mafia | jester
    is_alive: bool = True
    is_human: bool = False
    vigilante_shot_used: bool = False
    personality: str = ""


@dataclass
class NPCMemory:
    suspicions: dict = field(default_factory=dict)       # player_id -> float 0.0-1.0
    known_role: Optional[str] = None                      # last investigation summary (legacy)
    recent_speech: list = field(default_factory=list)
    investigations: dict = field(default_factory=dict)   # player_name -> "Mafia"/"Innocent" (sheriff only)
    saves: list = field(default_factory=list)             # player names protected each night (doctor only)


class GameState:
    def __init__(self):
        self.phase: str = "setup"
        self.round: int = 0
        self.mode: str = "player"
        self.players: list[Player] = []
        self.human_id: Optional[str] = None
        self.night_actions: dict = {}
        self.pending_action: Optional[dict] = None
        self.votes: dict = {}
        self.event_log: list[dict] = []
        self.winner: Optional[str] = None
        self.npc_memories: dict[str, NPCMemory] = {}
        self.doctor_last_save_id: Optional[str] = None
        self._lock = threading.Lock()
        self.tts_ack_event = threading.Event()

    def emit(self, event: dict):
        with self._lock:
            event.setdefault("phase", self.phase)
            event.setdefault("round", self.round)
            self.event_log.append(event)

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.is_alive]

    def alive_mafia(self) -> list[Player]:
        return [p for p in self.players if p.is_alive and p.team == "mafia"]

    def alive_town(self) -> list[Player]:
        return [p for p in self.players if p.is_alive and p.team == "town"]

    def get_player(self, player_id: str) -> Optional[Player]:
        return next((p for p in self.players if p.id == player_id), None)

    def get_human(self) -> Optional[Player]:
        if self.human_id:
            return self.get_player(self.human_id)
        return None

    def check_win(self) -> Optional[str]:
        mafia = self.alive_mafia()
        non_mafia = [p for p in self.players if p.is_alive and p.team != "mafia"]
        if not mafia:
            return "town"
        if len(mafia) >= len(non_mafia):
            return "mafia"
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
