from __future__ import annotations
import os
import random
from openai import OpenAI

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get("PERPLEXITY_API_KEY", "")
        if not key:
            raise RuntimeError("PERPLEXITY_API_KEY manquante dans le fichier .env")
        _client = OpenAI(
            api_key=key,
            base_url="https://api.perplexity.ai",
        )
    return _client


def _call(system: str, user: str, model: str, max_tokens: int, temperature: float) -> str:
    try:
        resp = get_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[Erreur IA : {e}]"


# ---------------------------------------------------------------------------
# Narration dramatique (sonar-pro, qualité max, peu d'appels)
# ---------------------------------------------------------------------------
_NARRATOR_SYSTEM = (
    "Tu es le narrateur mystérieux d'une partie de Loup-Garou dans un village français du XIXe siècle. "
    "Tu racontes les événements en français, d'une voix dramatique et immersive, comme un conteur de fables sombres. "
    "Sois concis : 2 à 4 phrases maximum par événement. "
    "N'utilise jamais le mot 'je'. Ne révèle jamais les rôles secrets des joueurs vivants. "
    "Utilise des descriptions sensorielles (sons, odeurs, ombres)."
)


def narrate(event_description: str) -> str:
    return _call(
        system=_NARRATOR_SYSTEM,
        user=event_description,
        model="sonar-pro",
        max_tokens=250,
        temperature=0.85,
    )


# ---------------------------------------------------------------------------
# Dialogue PNJ (sonar, bon marché, nombreux appels)
# ---------------------------------------------------------------------------
def npc_dialogue(
    npc_name: str,
    npc_role_cover: str,
    suspicions: dict[str, float],
    recent_speech: list[str],
    alive_names: list[str],
    dead_names: list[str],
    last_victim: str | None,
    human_last_message: str | None,
    round_num: int,
) -> str:
    sus_lines = ", ".join(
        f"{name} (suspicion {int(score * 100)}%)"
        for name, score in sorted(suspicions.items(), key=lambda x: -x[1])
        if score > 0.1
    ) or "personne en particulier"

    context_lines = []
    if last_victim:
        context_lines.append(f"Cette nuit, {last_victim} a été tué.")
    if human_last_message:
        context_lines.append(f"Le joueur humain vient de dire : « {human_last_message} »")
    if recent_speech:
        context_lines.append("Ce qui a déjà été dit : " + " | ".join(recent_speech[-3:]))

    system = (
        f"Tu joues le rôle de {npc_name} dans une partie de Loup-Garou. "
        f"Tu te présentes comme {npc_role_cover} au village. "
        f"Joueurs vivants : {', '.join(alive_names)}. "
        f"Morts : {', '.join(dead_names) if dead_names else 'aucun'}. "
        f"Tes suspicions actuelles : {sus_lines}. "
        "Réponds uniquement en français, 1 à 3 phrases courtes et naturelles. "
        "Tu dois accuser quelqu'un, te défendre, ou poser une question. Sois direct et humain. "
        "Ne mentionne pas que tu es une IA. Ne dis pas 'en tant que villageois'."
    )
    user = "\n".join(context_lines) if context_lines else f"C'est le tour {round_num}, que dis-tu ?"

    return _call(system=system, user=user, model="sonar", max_tokens=120, temperature=0.9)


# ---------------------------------------------------------------------------
# Vote PNJ (sonar, très bon marché, retourne un prénom strict)
# ---------------------------------------------------------------------------
def npc_vote(
    npc_name: str,
    suspicions: dict[str, float],
    candidates: list[str],
    round_num: int,
) -> str:
    if not candidates:
        return ""

    sus_lines = ", ".join(
        f"{name} (suspicion {int(score * 100)}%)"
        for name, score in sorted(suspicions.items(), key=lambda x: -x[1])
        if score > 0.05
    ) or "personne"

    system = (
        f"Tu joues {npc_name} dans une partie de Loup-Garou. "
        f"Tes suspicions : {sus_lines}. "
        "Tu dois voter pour éliminer quelqu'un. "
        f"Réponds UNIQUEMENT avec l'un de ces prénoms exacts, rien d'autre : {', '.join(candidates)}."
    )
    user = f"Tour {round_num}. Qui votes-tu pour éliminer ?"

    result = _call(system=system, user=user, model="sonar", max_tokens=15, temperature=0.3)

    # Parsing strict : trouver un prénom de la liste dans la réponse
    for name in candidates:
        if name.lower() in result.lower():
            return name
    return random.choice(candidates)


# ---------------------------------------------------------------------------
# Dialogue des loups (nuit, privé)
# ---------------------------------------------------------------------------
def wolf_deliberation(
    wolf_name: str,
    wolf_names: list[str],
    target_candidates: list[str],
    round_num: int,
) -> str:
    system = (
        f"Tu joues {wolf_name}, un loup-garou, en train de chuchoter avec tes congénères {', '.join(wolf_names)}. "
        "Vous choisissez votre prochain repas. Parle en français, 1-2 phrases, style sombre et complice. "
        f"Propose ou commente sur l'un de ces villageois : {', '.join(target_candidates)}."
    )
    user = f"Nuit {round_num}. Quel villageois doit mourir ?"

    return _call(system=system, user=user, model="sonar", max_tokens=80, temperature=0.9)


# ---------------------------------------------------------------------------
# Décision IA : sorcière
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
            # Cible la personne la plus suspectée
            best = max(
                [(n, suspicions.get(n, 0)) for n in candidates],
                key=lambda x: x[1],
            )
            if best[1] > 0.3:
                decision["kill_target"] = best[0]

    return decision
