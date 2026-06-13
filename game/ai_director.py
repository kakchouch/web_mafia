from __future__ import annotations
import json
import random
import urllib.request
from game import config as cfg


def reset_client():
    """No-op — conservé pour compatibilité avec app.py."""
    pass


def _native_url() -> str:
    """Dérive l'URL de l'API native Ollama (/api/chat) depuis OLLAMA_BASE_URL."""
    base = str(cfg.get("OLLAMA_BASE_URL")).rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return f"{base}/api/chat"


def _call(system: str, user: str, model: str, max_tokens: int, temperature: float) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream": False,
        "options": {
            "num_ctx":     int(cfg.get("OLLAMA_CTX_SIZE")),
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            _native_url(),
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        return result.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"[Erreur IA : {e}]"


# ---------------------------------------------------------------------------
# Règles du jeu — insérées dans tous les system prompts
# ---------------------------------------------------------------------------
_RULES = """
RÈGLES DU JEU LOUP-GAROU :
Le village et les loups-garous s'affrontent. Chaque nuit, les loups choisissent secrètement une victime à tuer. Chaque jour, tout le village vote pour éliminer un suspect. Le village gagne quand tous les loups sont éliminés. Les loups gagnent quand ils sont au moins aussi nombreux que les villageois.

RÔLES :
- Loup-garou : tue un villageois chaque nuit avec ses congénères. Se fait passer pour un innocent le jour.
- Villageois : aucun pouvoir spécial, vote le jour pour trouver les loups.
- Voyante : chaque nuit, découvre le vrai rôle d'un joueur.
- Sorcière : possède une potion de vie (sauver la victime des loups) et une potion de mort (tuer n'importe qui). Chacune utilisable une seule fois.
- Chasseur : à sa mort, peut immédiatement abattre un autre joueur.
- Cupidon : la première nuit, unit deux amoureux. Si l'un meurt, l'autre meurt de chagrin.
"""

# Instruction anti-markdown — mise EN PREMIER dans chaque système et répétée dans le user
_NO_MD = (
    "RÈGLE ABSOLUE : réponds en texte brut, prose française uniquement. "
    "INTERDIT : astérisques, **gras**, *italique*, # titres, - listes, ``` blocs, "
    "tirets, underscores de formatage, ou tout autre caractère markdown. "
    "Une seule phrase ou plusieurs phrases normales, c'est tout."
)
_NO_MD_REMINDER = "[Rappel : prose brute, zéro markdown.]\n"


# ---------------------------------------------------------------------------
# Historique de partie — formaté pour le system prompt
# ---------------------------------------------------------------------------

def _format_history(event_log: list[dict], is_wolf: bool = False) -> str:
    """Formate le log complet en texte lisible inséré dans le system prompt."""
    lines: list[str] = []
    current_phase_key: tuple | None = None
    phase_labels = {"nuit": "NUIT", "jour": "JOUR", "vote": "VOTE"}

    for evt in event_log:
        t = evt.get("type", "")
        phase = evt.get("phase", "")
        rnd = evt.get("round", "")

        phase_key = (phase, rnd)
        if phase_key != current_phase_key and phase in phase_labels:
            lines.append(f"\n--- {phase_labels[phase]} {rnd} ---")
            current_phase_key = phase_key

        if t == "narration":
            text = evt.get("text", "")
            if text:
                lines.append(f"[Narrateur] {text}")
        elif t == "npc_dialogue":
            speaker = evt.get("speaker", "?")
            text = evt.get("text", "")
            if text:
                lines.append(f"{speaker} : {text}")
        elif t == "wolf_private" and is_wolf:
            speaker = evt.get("speaker", "")
            text = evt.get("text", "")
            if text:
                prefix = f"[Loups — {speaker}]" if speaker else "[Loups]"
                lines.append(f"{prefix} {text}")
        elif t == "death":
            text = evt.get("text", "")
            if text:
                lines.append(f"[MORT] {text}")
        elif t == "vote_result":
            text = evt.get("text", "")
            if text:
                lines.append(f"[Votes] {text}")

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Narration dramatique
# ---------------------------------------------------------------------------
_NARRATOR_SYSTEM = (
    _NO_MD + "\n\n"
    + _RULES + "\n\n"
    "Tu es le narrateur d'une partie de Loup-Garou dans un village français du XIXe siècle. "
    "Tu racontes en français, voix dramatique et immersive, comme un conteur de fables sombres. "
    "2 à 4 phrases maximum. N'utilise jamais le mot 'je'. "
    "Ne révèle pas les rôles secrets des vivants. "
    "Descriptions sensorielles : sons, odeurs, ombres."
)


def narrate(event_description: str, event_log: list[dict] | None = None) -> str:
    history = _format_history(event_log or [])
    history_block = f"\n\nHISTORIQUE DE LA PARTIE :\n{history}" if history else ""
    system = _NARRATOR_SYSTEM + history_block
    return _call(
        system=system,
        user=_NO_MD_REMINDER + event_description,
        model=str(cfg.get("OLLAMA_MODEL")),
        max_tokens=int(cfg.get("AI_NARRATION_MAX_TOKENS")),
        temperature=float(cfg.get("AI_NARRATION_TEMPERATURE")),
    )


# ---------------------------------------------------------------------------
# Dialogue PNJ
# ---------------------------------------------------------------------------
def npc_dialogue(
    npc_name: str,
    npc_role_cover: str,
    suspicions: dict[str, float],
    recent_speech: list[str],
    alive_names: list[str],
    dead_events: list[str],
    last_victim: str | None,
    human_last_message: str | None,
    round_num: int,
    human_name: str | None = None,
    event_log: list[dict] | None = None,
    is_wolf: bool = False,
) -> str:
    sus_lines = ", ".join(
        f"{name} (suspicion {int(score * 100)}%)"
        for name, score in sorted(suspicions.items(), key=lambda x: -x[1])
        if score > 0.1
    ) or "personne en particulier"

    history = _format_history(event_log or [], is_wolf=is_wolf)
    history_block = f"\n\nHISTORIQUE COMPLET DE LA PARTIE :\n{history}" if history else ""

    system = (
        _NO_MD + "\n\n"
        + _RULES + "\n\n"
        f"Tu joues {npc_name} dans une partie de Loup-Garou. "
        f"Tu te présentes comme {npc_role_cover} au village. "
        f"Vivants : {', '.join(alive_names)}. "
        f"Morts : {'; '.join(dead_events) if dead_events else 'aucun'}. "
        f"Tes suspicions parmi les vivants : {sus_lines}. "
        "RÈGLE : ne parle jamais de suspicion envers un joueur déjà mort. "
        "1 à 3 phrases courtes, naturelles, en français. "
        "Accuse, défends-toi, pose une question précise à quelqu'un, ou interpelle un vivant. "
        f"Ne parle jamais de toi à la 3ème personne, ni à la 2ème personne, tu es {npc_name}. "
        "Sois humain, direct, impliqué dans le débat."
        + history_block
    )

    context_lines = [_NO_MD_REMINDER]
    if last_victim:
        context_lines.append(f"Cette nuit, {last_victim} a été tué.")
    if human_last_message:
        context_lines.append(
            f"Le joueur {human_name or 'humain'} vient de dire : « {human_last_message} » "
            "Réagis à ce qu'il dit."
        )
    if recent_speech:
        context_lines.append("Tes dernières répliques : " + " | ".join(recent_speech[-4:]))
    context_lines.append(f"Tour {round_num}. Que dis-tu ?")

    return _call(system=system, user="\n".join(context_lines),
                 model=str(cfg.get("OLLAMA_MODEL")),
                 max_tokens=int(cfg.get("AI_DIALOGUE_MAX_TOKENS")),
                 temperature=float(cfg.get("AI_DIALOGUE_TEMPERATURE")))


# ---------------------------------------------------------------------------
# Vote PNJ — raisonnement depuis l'état du jeu
# ---------------------------------------------------------------------------
def npc_vote(
    npc_name: str,
    npc_role: str,
    ally_names: list[str],
    candidates: list[str],
    dead_events: list[str],
    recent_discussion: list[str],
    round_num: int,
    event_log: list[dict] | None = None,
    is_wolf: bool = False,
) -> str:
    """Retourne UN prénom exact parmi candidates, ou '' si non parsable (→ fallback suspicion)."""
    if not candidates:
        return ""

    ally_hint = (
        f"Tes alliés loups : {', '.join(ally_names)}. "
        "En principe, ne vote pas pour eux — SAUF si les soupçons du village sont massivement "
        "dirigés contre l'un d'eux et que voter autrement te ferait repérer : dans ce cas, "
        "sacrifie-les pour te fondre dans la masse. "
        if ally_names else ""
    )

    history = _format_history(event_log or [], is_wolf=is_wolf)
    history_block = f"\n\nHISTORIQUE COMPLET DE LA PARTIE :\n{history}" if history else ""

    system = (
        _NO_MD + "\n\n"
        + _RULES + "\n\n"
        f"Tu joues {npc_name} dans une partie de Loup-Garou (ton rôle réel : {npc_role}). "
        f"{ally_hint}"
        f"Morts et causes : {'; '.join(dead_events) if dead_events else 'personne encore'}. "
        f"Candidats au vote : {', '.join(candidates)}. "
        "Réponds UNIQUEMENT avec UN seul prénom exact parmi les candidats. "
        "Raisonne depuis les morts, les comportements suspects et la discussion."
        + history_block
    )

    discussion_block = "\n".join(recent_discussion[-6:]) if recent_discussion else ""
    user = (
        _NO_MD_REMINDER
        + (f"Discussion de ce tour :\n{discussion_block}\n\n" if discussion_block else "")
        + f"Tour {round_num}. Écris uniquement le prénom de ta cible de vote."
    )

    result = _call(system=system, user=user, model=str(cfg.get("OLLAMA_MODEL")),
                   max_tokens=int(cfg.get("AI_VOTE_MAX_TOKENS")),
                   temperature=float(cfg.get("AI_VOTE_TEMPERATURE")))

    for name in candidates:
        if name.lower() in result.lower():
            return name
    return ""  # non parsable → fallback suspicion dans phases.py


# ---------------------------------------------------------------------------
# Dialogue des loups (nuit)
# ---------------------------------------------------------------------------
def wolf_deliberation(
    wolf_name: str,
    wolf_names: list[str],
    target_candidates: list[str],
    round_num: int,
    event_log: list[dict] | None = None,
) -> str:
    history = _format_history(event_log or [], is_wolf=True)
    history_block = f"\n\nHISTORIQUE COMPLET DE LA PARTIE :\n{history}" if history else ""

    system = (
        _NO_MD + "\n\n"
        + _RULES + "\n\n"
        f"Tu joues {wolf_name}, loup-garou, chuchotant avec {', '.join(wolf_names)}. "
        "1 à 2 phrases sombres et complices en français. "
        f"Propose ou commente l'un de ces villageois : {', '.join(target_candidates)}."
        + history_block
    )
    user = _NO_MD_REMINDER + f"Nuit {round_num}. Quel villageois doit mourir ?"

    return _call(system=system, user=user, model=str(cfg.get("OLLAMA_MODEL")),
                 max_tokens=int(cfg.get("AI_WOLF_MAX_TOKENS")),
                 temperature=float(cfg.get("AI_WOLF_TEMPERATURE")))


# ---------------------------------------------------------------------------
# Décision IA : sorcière (logique pure, pas d'appel IA)
# ---------------------------------------------------------------------------
def witch_ai_decision(
    victim_name: str,
    heal_available: bool,
    kill_available: bool,
    alive_names: list[str],
    suspicions: dict[str, float],
) -> dict:
    decision = {"heal": False, "kill_target": None}

    if heal_available and random.random() < 0.65:
        decision["heal"] = True

    if kill_available and not decision["heal"] and random.random() < 0.40:
        candidates = [n for n in alive_names if n != victim_name]
        if candidates:
            best = max([(n, suspicions.get(n, 0)) for n in candidates], key=lambda x: x[1])
            if best[1] > 0.3:
                decision["kill_target"] = best[0]

    return decision
