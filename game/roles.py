from __future__ import annotations

NIGHT_ORDER = ["cupidon", "loup-garou", "voyante", "sorciere", "chasseur"]

ROLE_CONFIGS = {
    "loup-garou": {
        "team": "loups",
        "label": "Loup-Garou",
        "emoji": "🐺",
        "description": "La nuit, vous vous réveillez avec vos congénères et choisissez une victime à dévorer.",
        "night_action": True,
    },
    "villageois": {
        "team": "village",
        "label": "Villageois",
        "emoji": "👨‍🌾",
        "description": "Vous n'avez aucun pouvoir spécial, mais votre vote compte pendant le jour.",
        "night_action": False,
    },
    "voyante": {
        "team": "village",
        "label": "Voyante",
        "emoji": "🔮",
        "description": "Chaque nuit, vous pouvez découvrir la vraie identité d'un joueur.",
        "night_action": True,
    },
    "sorciere": {
        "team": "village",
        "label": "Sorcière",
        "emoji": "🧙",
        "description": "Vous possédez une potion de vie (sauver la victime des loups) et une potion de mort (éliminer n'importe qui). Chacune est utilisable une seule fois.",
        "night_action": True,
    },
    "chasseur": {
        "team": "village",
        "label": "Chasseur",
        "emoji": "🏹",
        "description": "Quand vous mourez, vous pouvez immédiatement abattre un autre joueur.",
        "night_action": False,
    },
    "cupidon": {
        "team": "village",
        "label": "Cupidon",
        "emoji": "💘",
        "description": "La première nuit, vous désignez deux amoureux. Si l'un meurt, l'autre mourra de chagrin.",
        "night_action": True,
    },
}

# Composition par nombre de joueurs
ROLE_POOLS = {
    4: ["loup-garou", "voyante", "villageois", "villageois"],
    5: ["loup-garou", "voyante", "sorciere", "villageois", "villageois"],
    6: ["loup-garou", "loup-garou", "voyante", "sorciere", "chasseur", "villageois"],
    7: ["loup-garou", "loup-garou", "voyante", "sorciere", "chasseur", "villageois", "villageois"],
    8: ["loup-garou", "loup-garou", "voyante", "sorciere", "chasseur", "cupidon", "villageois", "villageois"],
}

FRENCH_NAMES = [
    "Marie", "Pierre", "Sophie", "Jean", "Isabelle", "Thomas",
    "Camille", "Nicolas", "Lucie", "Antoine", "Emma", "Julien",
    "Léa", "Maxime", "Clara", "François", "Chloé", "Romain",
    "Manon", "Gabriel",
]

WIN_CONDITIONS = {
    "village": "Le village a éliminé tous les loups-garous ! La paix est revenue.",
    "loups": "Les loups-garous dominent le village ! La nuit est tombée pour toujours.",
    "amoureux": "Les deux amoureux sont les derniers survivants. Leur amour triomphe de tout !",
}
