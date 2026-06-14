from __future__ import annotations
import json
import random
import urllib.request
from game import config as cfg


def reset_client():
    pass


def _native_url() -> str:
    base = str(cfg.get("OLLAMA_BASE_URL")).rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return f"{base}/api/chat"


def _call(system: str, user: str, model: str, max_tokens: int,
          temperature: float, top_p: float = 1.0, top_k: int = 40) -> str:
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
            "top_p":       top_p,
            "top_k":       top_k,
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
        return f"[AI Error: {e}]"


# ---------------------------------------------------------------------------
# Game rules — inserted in all system prompts
# ---------------------------------------------------------------------------
_RULES = """
GAME RULES — MAFIA:
The town faces the mafia in a battle of deception. Each night, the mafia secretly chooses a player to eliminate. Each day, all players vote to eliminate a suspect. The town wins when all mafia are eliminated. The mafia wins when they equal or outnumber the town.

ROLES:
- Mafia: each night, eliminate a town member with your partners. Blend in during the day.
- Villager: no special power; vote during the day to find the mafia.
- Sheriff: each night, investigate one player to learn if they are Mafia or Innocent.
- Doctor: each night, protect one player from being killed. Cannot protect the same person two nights in a row.
- Vigilante: once per game, can shoot a player at night. Shooting an innocent causes the vigilante to die of guilt.
- Jester: wins if voted out by the town. Appears Innocent to the Sheriff.

REMINDERS:
- Mafia cannot kill other mafia members at night;
- The Jester appears as Innocent to the Sheriff;
- No player changes role during the game.
"""

# ---------------------------------------------------------------------------
# NPC personality profiles
# ---------------------------------------------------------------------------
NPC_PROFILES: dict[str, str] = {
    "calculating": (
        "PROFILE — CALCULATING: You observe carefully before acting. "
        "You cite specific facts and event numbers to support your arguments. "
        "You speak little but each word is deliberate. Once you have a target, you don't change. "
        "Your tone is cold, measured, never emotional. You deduce; you don't accuse lightly."
    ),
    "aggressive": (
        "PROFILE — AGGRESSIVE: You attack directly and without mercy. "
        "You raise your voice easily and push others to their limits. "
        "You don't like being contradicted and you make it known. "
        "Your tone is sharp, sometimes threatening. You create confrontations to expose weaknesses."
    ),
    "anxious": (
        "PROFILE — ANXIOUS: You hesitate, you voice your doubts out loud. "
        "You may contradict yourself from one round to the next. You seek confirmation from others. "
        "Your tone is nervous, with phrases like 'I'm afraid that…', 'I'm not sure if…'. "
        "You worry about everyone and you show it."
    ),
    "manipulative": (
        "PROFILE — MANIPULATIVE: You never defend yourself directly. "
        "You ask rhetorical questions, you turn accusations back on the accuser. "
        "You subtly sow doubt, you make others say what you want. "
        "Your tone is smooth, calm, never brutal. You smile between the words."
    ),
    "naive": (
        "PROFILE — NAIVE: You trust easily and are influenced by what you just heard. "
        "Your accusations are emotional rather than logical. "
        "You may change your mind mid-round if someone convinces you. "
        "Your tone is sincere, candid, sometimes awkward."
    ),
    "leader": (
        "PROFILE — LEADER: You take charge, propose votes, organize the debate. "
        "You call out the quiet ones by name; you rally people around you. "
        "Your tone is confident, authoritative without being aggressive. "
        "You have a firm opinion and defend it with conviction."
    ),
    "discreet": (
        "PROFILE — DISCREET: You answer briefly, you avoid the spotlight. "
        "When you speak, it is targeted, precise, surgical. You never attack first. "
        "But you have observed everything and you reveal it at the right moment. "
        "Your tone is calm, economical with words, slightly mysterious."
    ),
    "emotional": (
        "PROFILE — EMOTIONAL: You react strongly to deaths and revelations. "
        "You can be swept up by fear or anger. "
        "You place great importance on the relationships between players. "
        "Your tone is warm or shaken depending on the situation. "
        "You use empathy as an argument ('how can you say that after what happened?')."
    ),
    "logical": (
        "PROFILE — LOGICAL: You reason methodically and systematically. "
        "You reference past votes and events by their index number. "
        "You eliminate impossibilities before accusing. "
        "Your tone is neutral, analytical, almost clinical. "
        "You only accuse when you have a sufficient body of evidence."
    ),
    "performer": (
        "PROFILE — PERFORMER: You dramatize, you exaggerate your reactions to make an impression. "
        "You can be theatrical in your indignation or suspicions. "
        "You use dark humor or sarcasm on occasion. "
        "Your tone is expressive, lively, sometimes over the top — but it diverts attention."
    ),
}

# Sampling params tuned per personality archetype.
# Low temp + low top_p + low top_k = precise, predictable (logical, discreet, calculating).
# High temp + high top_p + high top_k = expressive, varied (emotional, performer, naive, aggressive).
PROFILE_PARAMS: dict[str, dict] = {
    #                               temp   top_p  top_k
    "calculating":  {"temperature": 0.50, "top_p": 0.85, "top_k": 25},
    "aggressive":   {"temperature": 1.20, "top_p": 0.95, "top_k": 70},
    "anxious":      {"temperature": 1.10, "top_p": 0.92, "top_k": 60},
    "manipulative": {"temperature": 0.70, "top_p": 0.88, "top_k": 40},
    "naive":        {"temperature": 1.20, "top_p": 0.98, "top_k": 80},
    "leader":       {"temperature": 0.60, "top_p": 0.85, "top_k": 35},
    "discreet":     {"temperature": 0.40, "top_p": 0.80, "top_k": 20},
    "emotional":    {"temperature": 1.30, "top_p": 0.97, "top_k": 90},
    "logical":      {"temperature": 0.30, "top_p": 0.75, "top_k": 15},
    "performer":    {"temperature": 1.30, "top_p": 0.97, "top_k": 90},
}

# ---------------------------------------------------------------------------
# NPC strategy heuristics
# ---------------------------------------------------------------------------
_NPC_STRATEGY = """
STRATEGY HEURISTICS AND BEHAVIORS:

General behavior (all roles):
- Silence is suspicious. Participate, ask questions, take a stance.
- You may abstain from voting when you have no strong suspicion — say "I abstain" and explain why. But abstaining repeatedly makes you look passive and suspicious.
- A strict majority is required to eliminate someone. Abstentions count against the target, so coordinating abstentions can protect an innocent.
- Reference specific past events by their index number: "at event (5), Bob voted for Alice without explanation."
- Be wary of players who change targets too quickly or accuse without solid arguments.
- Cross-reference votes: players who consistently vote together may be allied.
- If someone has never been targeted at night despite suspicion, the mafia may be protecting them.
- Someone who defends an eliminated player too passionately may have been their ally.

If you are on the town side (villager, sheriff, doctor, vigilante):
- Look for inconsistencies: someone who says they suspect X but votes for Y is suspicious.
- Mafia often vote together — compare votes from previous rounds.
- If you are the sheriff and know a dangerous role, guide suspicion subtly without revealing your identity.
- If you are the vigilante, keep your identity secret as long as possible.
- If you are the doctor, don't reveal yourself unless it's critical.
- A player eliminated whose role was innocent should redirect suspicion toward those who voted for them.

If you are mafia:
- Never vote for a mafia ally unless town pressure is unanimous against them — sacrifice them then to appear credible.
- Don't always vote in a bloc with your partners — vote differently to hide the alliance.
- Progressively build suspicion on the same innocent from the start, in a credible way.
- Aim to direct the town toward the sheriff or doctor.
- Be active, reasonable, propose arguments — a silent mafia member betrays themselves.
- Never defend a mafia member who was just eliminated: that's a strong signal.
"""

_NO_MD = (
    "ABSOLUTE RULE: respond in plain text, English prose only. "
    "FORBIDDEN: asterisks, **bold**, *italic*, # headings, - lists, ``` blocks, "
    "dashes, formatting underscores, or any other markdown characters. "
    "One sentence or several normal sentences only."
)
_NO_MD_REMINDER = "[Reminder: plain prose, zero markdown.]\n"


# ---------------------------------------------------------------------------
# Game history formatter
# ---------------------------------------------------------------------------

def _format_history(event_log: list[dict], is_mafia: bool = False) -> str:
    lines: list[str] = []
    current_phase_key: tuple | None = None
    phase_labels = {"night": "NIGHT", "day": "DAY", "vote": "VOTE"}
    idx = 0

    for evt in event_log:
        t = evt.get("type", "")
        phase = evt.get("phase", "")
        rnd = evt.get("round", "")

        phase_key = (phase, rnd)
        if phase_key != current_phase_key and phase in phase_labels:
            lines.append(f"\n--- {phase_labels[phase]} {rnd} ---")
            current_phase_key = phase_key

        entry: str | None = None
        if t == "narration":
            text = evt.get("text", "")
            if text:
                entry = f"[Narrator] {text}"
        elif t == "npc_dialogue":
            text = evt.get("text", "")
            if text:
                entry = f"{evt.get('speaker', '?')}: {text}"
        elif t == "mafia_private" and is_mafia:
            text = evt.get("text", "")
            if text:
                speaker = evt.get("speaker", "")
                prefix = f"[Mafia — {speaker}]" if speaker else "[Mafia]"
                entry = f"{prefix} {text}"
        elif t == "death":
            text = evt.get("text", "")
            if text:
                entry = f"[DEATH] {text}"
        elif t == "vote_result":
            text = evt.get("text", "")
            if text:
                entry = f"[Votes] {text}"

        if entry is not None:
            idx += 1
            lines.append(f"({idx}) {entry}")

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Dramatic narration
# ---------------------------------------------------------------------------
_NARRATOR_SYSTEM = (
    _NO_MD + "\n\n"
    + _RULES + "\n\n"
    "You are the narrator of a Mafia game set in a small American town. "
    "Respond in English. 1 sentence only — no more. Never use the word 'I'. "
    "Do not reveal the secret roles of living players. Be punchy and atmospheric."
)


def narrate(event_description: str, event_log: list[dict] | None = None) -> str:
    history = _format_history(event_log or [])
    history_block = f"\n\nGAME HISTORY:\n{history}" if history else ""
    system = _NARRATOR_SYSTEM + history_block
    return _call(
        system=system,
        user=_NO_MD_REMINDER + event_description,
        model=str(cfg.get("OLLAMA_MODEL")),
        max_tokens=int(cfg.get("AI_NARRATION_MAX_TOKENS")),
        temperature=float(cfg.get("AI_NARRATION_TEMPERATURE")),
    )


# ---------------------------------------------------------------------------
# NPC dialogue
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
    is_mafia: bool = False,
    personality: str = "",
    private_context: str = "",
) -> str:
    sus_lines = ", ".join(
        f"{name} (suspicion {int(score * 100)}%)"
        for name, score in sorted(suspicions.items(), key=lambda x: -x[1])
        if score > 0.1
    ) or "nobody in particular"

    history = _format_history(event_log or [], is_mafia=is_mafia)
    history_block = f"\n\nFULL GAME HISTORY:\n{history}" if history else ""
    personality_block = f"\n\n{NPC_PROFILES[personality]}" if personality in NPC_PROFILES else ""

    role_block = f"\n{private_context}" if private_context else ""

    dialogue_guidelines = f"Never refer to yourself in the 3rd or 2nd person, you are {npc_name}. "
    "ALWAYS speak as yourself using 'I', never refer to yourself in third person."
    "Never repeat word for word previous messages."
    "Do not mention any behavior that cannot be deduced by the text-based game history (e.g. eye contacts)."
    f"Keep in mind there are no two people with the same name. Anywhere {npc_name} is mentionned, YOU are mentionned."
    "Be human, direct, engaged in the debate."



    system = (
        _NO_MD + "\n\n"
        + _RULES
        + _NPC_STRATEGY
        + personality_block
        + role_block + "\n\n"
        f"You are playing {npc_name} in a game of Mafia. "
        f"You claim to be a {npc_role_cover} to the town. "
        f"Alive: {', '.join(alive_names)}. "
        f"Dead: {'; '.join(dead_events) if dead_events else 'none'}. "
        f"Your suspicions among the living: {sus_lines}. "
        "CRITICAL RULE: never name or accuse a dead player — they are gone, ignore them. "
        "1 to 3 short, natural English sentences. "
        "Accuse, defend yourself, ask someone a pointed question, or call out a living player. "
        "Draw on what others have said and the game history to support your suspicions. "
        + dialogue_guidelines
        + history_block
        + "\nREMINDER: nothing has happened outside of the game history."
    )

    context_lines = [_NO_MD_REMINDER]
    if last_victim:
        context_lines.append(f"Tonight, {last_victim} was killed.")
    if human_last_message:
        context_lines.append(
            f"Player {human_name or 'human'} just said: \"{human_last_message}\" "
            "React to what they said."
        )
    if recent_speech:
        context_lines.append("Your recent lines: " + " | ".join(recent_speech[-4:]))
    context_lines.append(f"Round {round_num}. What do you say?")

    params = PROFILE_PARAMS.get(personality, {"temperature": float(cfg.get("AI_DIALOGUE_TEMPERATURE")), "top_p": 1.0, "top_k": 40})
    return _call(system=system, user="\n".join(context_lines),
                 model=str(cfg.get("OLLAMA_MODEL")),
                 max_tokens=int(cfg.get("AI_DIALOGUE_MAX_TOKENS")),
                 temperature=params["temperature"],
                 top_p=params["top_p"],
                 top_k=params["top_k"])


# ---------------------------------------------------------------------------
# NPC vote with argument
# ---------------------------------------------------------------------------
def npc_vote_aloud(
    npc_name: str,
    npc_role: str,
    ally_names: list[str],
    candidates: list[str],
    dead_events: list[str],
    round_num: int,
    event_log: list[dict] | None = None,
    is_mafia: bool = False,
    personality: str = "",
    private_context: str = "",
) -> str:
    if not candidates:
        return ""

    ally_hint = (
        f"Your mafia allies: {', '.join(ally_names)}. "
        "Never name them as targets unless town pressure is unanimous against them. "
        if ally_names else ""
    )

    history = _format_history(event_log or [], is_mafia=is_mafia)
    history_block = f"\n\nFULL GAME HISTORY:\n{history}" if history else ""
    personality_block = f"\n\n{NPC_PROFILES[personality]}" if personality in NPC_PROFILES else ""

    role_block = f"\n{private_context}" if private_context else ""

    dialogue_guidelines = f"Never refer to yourself in the 3rd or 2nd person, you are {npc_name}. "
    "ALWAYS speak as yourself using 'I', never refer to yourself in third person."
    "Never repeat word for word previous messages."
    "Do not mention any behavior that cannot be deduced by the text-based game history (e.g. eye contacts)."
    f"Keep in mind there are no two people with the same name. Anywhere {npc_name} is mentionned, YOU are mentionned."
    "Be human, direct, engaged in the debate."

    system = (
        _NO_MD + "\n\n"
        + _RULES
        + _NPC_STRATEGY
        + personality_block
        + role_block + "\n\n"
        f"You are playing {npc_name} (actual role: {npc_role}). "
        f"{ally_hint}"
        f"Dead players (cannot be voted): {'; '.join(dead_events) if dead_events else 'none'}. "
        f"Living candidates you CAN vote for: {', '.join(candidates)}. "
        "CRITICAL RULE: if you vote, your target MUST be one of the living candidates listed above. NEVER name a dead player. "
        "You may either vote for a living candidate OR abstain. "
        "To abstain: begin your statement with 'I abstain' and give a brief reason (not enough evidence, no clear suspect, too risky). "
        "To vote: name your target clearly — their exact name MUST appear in your 1-2 sentence statement — and justify with a concrete argument. "
        "Abstain only when you genuinely lack strong suspicion; abstaining too often looks suspicious."
        "Keep in mind that if the game involve 8 players or more, a jester might be lurking."
        "Lynching the jester hands them the win. This outcome is not desirable if you are not the jester yourself."
        + dialogue_guidelines
        + history_block
    )

    user = (
        _NO_MD_REMINDER
        + f"Round {round_num}. Publicly announce your vote and justify it in one or two sentences."
    )

    params = PROFILE_PARAMS.get(personality, {"temperature": float(cfg.get("AI_VOTE_TEMPERATURE")), "top_p": 1.0, "top_k": 40})
    return _call(system=system, user=user, model=str(cfg.get("OLLAMA_MODEL")),
                 max_tokens=int(cfg.get("AI_DIALOGUE_MAX_TOKENS")),
                 temperature=params["temperature"],
                 top_p=params["top_p"],
                 top_k=params["top_k"])


# ---------------------------------------------------------------------------
# Mafia night deliberation
# ---------------------------------------------------------------------------
def mafia_deliberation(
    mafia_name: str,
    mafia_names: list[str],
    target_candidates: list[str],
    round_num: int,
    event_log: list[dict] | None = None,
    personality: str = "",
) -> str:
    history = _format_history(event_log or [], is_mafia=True)
    history_block = f"\n\nFULL GAME HISTORY:\n{history}" if history else ""

    system = (
        _NO_MD + "\n\n"
        + _RULES + "\n\n"
        f"You are playing {mafia_name}, a mafia member, whispering with {', '.join(mafia_names)}. "
        "1 to 2 dark, conspiratorial English sentences. "
        f"Propose or comment on one of these town members: {', '.join(target_candidates)}."
        + history_block
    )
    user = _NO_MD_REMINDER + f"Night {round_num}. Who should die tonight?"

    params = PROFILE_PARAMS.get(personality, {"temperature": float(cfg.get("AI_WOLF_TEMPERATURE")), "top_p": 1.0, "top_k": 40})
    return _call(system=system, user=user, model=str(cfg.get("OLLAMA_MODEL")),
                 max_tokens=int(cfg.get("AI_WOLF_MAX_TOKENS")),
                 temperature=params["temperature"],
                 top_p=params["top_p"],
                 top_k=params["top_k"])


# ---------------------------------------------------------------------------
# AI decisions (pure logic, no LLM call)
# ---------------------------------------------------------------------------
def doctor_ai_decision(alive_names: list[str]) -> dict:
    if not alive_names:
        return {"save_target": None}
    return {"save_target": random.choice(alive_names)}


def vigilante_ai_decision(alive_names: list[str], suspicions: dict) -> dict:
    if not alive_names:
        return {"shoot_target": None}
    best = max([(n, suspicions.get(n, 0)) for n in alive_names], key=lambda x: x[1])
    if best[1] > 0.7:
        return {"shoot_target": best[0]}
    return {"shoot_target": None}
