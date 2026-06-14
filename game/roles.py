from __future__ import annotations

NIGHT_ORDER = ["mafia", "doctor", "sheriff", "vigilante"]

ROLE_CONFIGS = {
    "mafia": {
        "team": "mafia",
        "label": "Mafia",
        "emoji": "🔫",
        "description": "Each night, you and your partners secretly choose a target to eliminate. Blend in during the day.",
        "night_action": True,
    },
    "villager": {
        "team": "town",
        "label": "Villager",
        "emoji": "👤",
        "description": "You have no special power, but your vote matters. Root out the mafia!",
        "night_action": False,
    },
    "sheriff": {
        "team": "town",
        "label": "Sheriff",
        "emoji": "⭐",
        "description": "Each night, you may investigate one player to learn whether they are Mafia or Innocent.",
        "night_action": True,
    },
    "doctor": {
        "team": "town",
        "label": "Doctor",
        "emoji": "💉",
        "description": "Each night, protect one player from being killed. You cannot protect the same person two nights in a row.",
        "night_action": True,
    },
    "vigilante": {
        "team": "town",
        "label": "Vigilante",
        "emoji": "🎯",
        "description": "Once per game, you may shoot a player at night. Shooting an innocent causes you to die of guilt.",
        "night_action": True,
    },
    "jester": {
        "team": "jester",
        "label": "Jester",
        "emoji": "🃏",
        "description": "You win if the town votes you out during the day. Act suspicious without being too obvious!",
        "night_action": False,
    },
}

ROLE_POOLS = {
    4:  ["mafia", "sheriff", "villager", "villager"],
    5:  ["mafia", "sheriff", "doctor", "villager", "villager"],
    6:  ["mafia", "mafia", "sheriff", "doctor", "vigilante", "villager"],
    7:  ["mafia", "mafia", "sheriff", "doctor", "vigilante", "villager", "villager"],
    8:  ["mafia", "mafia", "sheriff", "doctor", "vigilante", "jester", "villager", "villager"],
    9:  ["mafia", "mafia", "sheriff", "doctor", "vigilante", "jester", "villager", "villager", "villager"],
    10: ["mafia", "mafia", "mafia", "sheriff", "doctor", "vigilante", "jester", "villager", "villager", "villager"],
    11: ["mafia", "mafia", "mafia", "sheriff", "doctor", "vigilante", "jester", "villager", "villager", "villager", "villager"],
    12: ["mafia", "mafia", "mafia", "sheriff", "doctor", "vigilante", "jester", "villager", "villager", "villager", "villager", "villager"],
}

ENGLISH_NAMES: dict[str, str] = {
    "Alice": "f", "Bob": "m", "Charlie": "m", "Diana": "f",
    "Edward": "m", "Fiona": "f", "George": "m", "Hannah": "f",
    "Isaac": "m", "Julia": "f", "Kevin": "m", "Laura": "f",
    "Michael": "m", "Nancy": "f", "Oscar": "m", "Patricia": "f",
    "Quinn": "m", "Rachel": "f", "Steven": "m", "Tina": "f",
}

# Each name has a fixed personality — two names per profile.
NAME_PERSONALITY: dict[str, str] = {
    "Alice":    "manipulative",
    "Bob":      "aggressive",
    "Charlie":  "naive",
    "Diana":    "calculating",
    "Edward":   "logical",
    "Fiona":    "emotional",
    "George":   "discreet",
    "Hannah":   "leader",
    "Isaac":    "performer",
    "Julia":    "anxious",
    "Kevin":    "aggressive",
    "Laura":    "calculating",
    "Michael":  "leader",
    "Nancy":    "emotional",
    "Oscar":    "discreet",
    "Patricia": "manipulative",
    "Quinn":    "performer",
    "Rachel":   "logical",
    "Steven":   "naive",
    "Tina":     "anxious",
}

WIN_CONDITIONS = {
    "town": "The town has eliminated all mafia members! Justice is served.",
    "mafia": "The mafia has taken over the town! The streets belong to them now.",
    "jester": "The Jester wins! They played the town perfectly and got voted out.",
}
