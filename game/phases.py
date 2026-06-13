from __future__ import annotations
import random
from typing import TYPE_CHECKING

from game import ai_director as ai
from game import config as cfg
from game.roles import NIGHT_ORDER, WIN_CONDITIONS
from game.state import NPCMemory

if TYPE_CHECKING:
    from game.state import GameState, Player


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _names(players: list) -> list[str]:
    return [p.name for p in players]


def _kill_player(state: "GameState", player: "Player", cause: str = "loup"):
    player.is_alive = False
    state.emit({"type": "death", "player_id": player.id, "name": player.name, "cause": cause,
                "text": f"{player.name} est mort·e cette nuit."})

    # Si l'un des amoureux meurt, l'autre aussi
    if player.lover_id:
        lover = state.get_player(player.lover_id)
        if lover and lover.is_alive:
            lover.is_alive = False
            state.emit({"type": "death", "player_id": lover.id, "name": lover.name, "cause": "chagrin",
                        "text": f"{lover.name} meurt de chagrin, emporté·e par l'amour."})
            # Chasseur lover
            if lover.role == "chasseur":
                _chasseur_retaliation(state, lover)

    if player.role == "chasseur":
        _chasseur_retaliation(state, player)


def _chasseur_retaliation(state: "GameState", chasseur: "Player"):
    candidates = [p for p in state.alive_players() if p.id != chasseur.id]
    if not candidates:
        return

    state.emit({"type": "narration",
                "text": f"Dans son dernier souffle, {chasseur.name} empoigne son fusil…"})

    if chasseur.is_human and state.mode == "player":
        result = state.await_human_action("hunter_shoot", candidates)
        target_id = result["target_id"] if result else None
    else:
        # IA ou spectateur : cible le plus suspect
        mem = state.npc_memories.get(chasseur.id)
        if mem and mem.suspicions:
            best = max(
                [(p, mem.suspicions.get(p.id, 0)) for p in candidates],
                key=lambda x: x[1],
            )
            target_id = best[0].id
        else:
            target_id = random.choice(candidates).id

    target = state.get_player(target_id) if target_id else None
    if target and target.is_alive:
        _kill_player(state, target, cause="chasseur")
        state.emit({"type": "narration",
                    "text": f"{chasseur.name} a tiré sur {target.name} avant de s'éteindre."})


def _update_suspicions_after_vote(state: "GameState", eliminated: "Player", voters_for: list[str]):
    for npc_id, mem in state.npc_memories.items():
        if eliminated.team == "loups":
            # Bien voté : réduire suspicion sur les loups restants
            for w in state.alive_wolves():
                mem.suspicions[w.id] = min(1.0, mem.suspicions.get(w.id, 0) + 0.3)
        else:
            # Innocent tué : augmenter suspicion sur ceux qui ont voté pour lui
            for voter_id in voters_for:
                mem.suspicions[voter_id] = min(1.0, mem.suspicions.get(voter_id, 0) + 0.15)


# ---------------------------------------------------------------------------
# Phase NUIT
# ---------------------------------------------------------------------------

def run_night(state: "GameState"):
    state.phase = "nuit"
    alive = state.alive_players()

    narration = ai.narrate(
        f"Nuit {state.round} dans le village. Les habitants s'endorment, tremblants. "
        f"Il reste {len(alive)} joueurs.",
        event_log=state.event_log,
    )
    state.emit({"type": "narration", "text": narration})

    state.night_actions = {}

    for role in NIGHT_ORDER:
        if role == "cupidon" and state.round > 1:
            continue

        actors = [p for p in state.alive_players() if p.role == role]
        if not actors:
            continue

        if role == "cupidon":
            _night_cupidon(state, actors[0])
        elif role == "loup-garou":
            _night_wolves(state)
        elif role == "voyante":
            _night_voyante(state, actors[0])
        elif role == "sorciere":
            _night_sorciere(state, actors[0])

    # Appliquer les morts
    victim_id = state.night_actions.get("loup_victim")
    witch_saved = state.night_actions.get("witch_saved", False)
    witch_kill_id = state.night_actions.get("witch_kill")

    if victim_id and not witch_saved:
        victim = state.get_player(victim_id)
        if victim and victim.is_alive:
            _kill_player(state, victim, cause="loup")

    if witch_kill_id:
        target = state.get_player(witch_kill_id)
        if target and target.is_alive:
            _kill_player(state, target, cause="sorciere")

    winner = state.check_win()
    if winner:
        _end_game(state, winner)
        return

    run_jour(state)


def _night_cupidon(state: "GameState", cupidon: "Player"):
    candidates = [p for p in state.alive_players() if p.id != cupidon.id]
    if len(candidates) < 2:
        return

    state.emit({"type": "narration", "visible": "spectator_or_role:cupidon",
                "text": "Cupidon s'éveille et tend son arc vers deux âmes endormies…"})

    if cupidon.is_human and state.mode == "player":
        result = state.await_human_action("cupidon_choose", candidates,
                                          extra={"message": "Choisissez le premier amoureux"})
        lover1_id = result["target_id"] if result else candidates[0].id

        remaining = [p for p in candidates if p.id != lover1_id]
        result2 = state.await_human_action("cupidon_choose2", remaining,
                                           extra={"message": "Choisissez le second amoureux"})
        lover2_id = result2["target_id"] if result2 else remaining[0].id
    else:
        chosen = random.sample(candidates, 2)
        lover1_id, lover2_id = chosen[0].id, chosen[1].id

    l1, l2 = state.get_player(lover1_id), state.get_player(lover2_id)
    if l1 and l2:
        l1.lover_id = l2.id
        l2.lover_id = l1.id
        state.emit({"type": "lovers_set", "visible": "spectator_or_role:cupidon",
                    "lover1": l1.name, "lover2": l2.name,
                    "text": f"La flèche de Cupidon unit {l1.name} et {l2.name} pour l'éternité."})
        # Révéler aux amoureux s'ils sont humains
        human = state.get_human()
        if human and human.id in (lover1_id, lover2_id):
            partner = l2 if human.id == lover1_id else l1
            state.emit({"type": "lover_reveal", "visible": "human",
                        "text": f"[Secret] Vous êtes amoureux de {partner.name}."})


def _night_wolves(state: "GameState"):
    wolves = state.alive_wolves()
    candidates = state.alive_village()
    if not candidates:
        return

    human_wolf = next((p for p in wolves if p.is_human), None)
    wolf_names = _names(wolves)
    candidate_names = _names(candidates)

    # Délibération des loups IA
    # L'ACK TTS n'est attendu que si le joueur humain verra l'événement
    human = state.get_human()
    human_hears_wolves = state.mode == "spectator" or (human and human.team == "loups")

    for wolf in wolves:
        if not wolf.is_human:
            speech = ai.wolf_deliberation(wolf.name, wolf_names, candidate_names, state.round,
                                          event_log=state.event_log)
            if human_hears_wolves:
                state.tts_ack_event.clear()
            state.emit({"type": "wolf_private", "visible": "wolves",
                        "speaker": wolf.name, "text": speech})
            if human_hears_wolves:
                state.tts_ack_event.wait(timeout=int(cfg.get("TTS_ACK_TIMEOUT")))

    if human_wolf and state.mode == "player":
        result = state.await_human_action("wolf_vote", candidates)
        victim_id = result["target_id"] if result else random.choice(candidates).id
    else:
        # Choix de la victime : loup avec le plus de suspicion sur les villageois
        mem = state.npc_memories.get(wolves[0].id) if wolves else None
        chosen = _npc_vote_target(mem, candidates)
        victim_id = chosen.id if chosen else random.choice(candidates).id

    state.night_actions["loup_victim"] = victim_id
    victim = state.get_player(victim_id)
    state.emit({"type": "wolf_private", "visible": "wolves",
                "text": f"Les loups ont choisi {victim.name if victim else '?'}."})


def _night_voyante(state: "GameState", voyante: "Player"):
    candidates = [p for p in state.alive_players() if p.id != voyante.id]
    if not candidates:
        return

    state.emit({"type": "narration", "visible": "spectator_or_role:voyante",
                "text": "La Voyante ouvre son œil intérieur sur les ténèbres…"})

    if voyante.is_human and state.mode == "player":
        result = state.await_human_action("seer_reveal", candidates)
        target_id = result["target_id"] if result else random.choice(candidates).id
    else:
        # IA : cible le plus suspect ou aléatoire
        mem = state.npc_memories.get(voyante.id)
        if mem and mem.suspicions:
            best = max([(p, mem.suspicions.get(p.id, 0)) for p in candidates], key=lambda x: x[1])
            target_id = best[0].id
        else:
            target_id = random.choice(candidates).id

    target = state.get_player(target_id)
    if not target:
        return

    if voyante.is_human and state.mode == "player":
        state.emit({"type": "role_reveal", "visible": "human",
                    "target_name": target.name, "role": target.role,
                    "text": f"[Voyante] {target.name} est : {target.role}."})
    else:
        # Mémoriser pour le PNJ voyante
        mem = state.npc_memories.setdefault(voyante.id, NPCMemory())
        mem.known_role = f"{target.name} est {target.role}"
        if target.team == "loups":
            mem.suspicions[target.id] = 1.0

    state.emit({"type": "role_reveal", "visible": "spectator",
                "target_name": target.name, "role": target.role,
                "text": f"[Spectateur] La Voyante découvre que {target.name} est {target.role}."})


def _night_sorciere(state: "GameState", sorciere: "Player"):
    victim_id = state.night_actions.get("loup_victim")
    victim = state.get_player(victim_id) if victim_id else None

    heal_available = not sorciere.witch_heal_used
    kill_available = not sorciere.witch_kill_used

    if not heal_available and not kill_available:
        return

    state.emit({"type": "narration", "visible": "spectator_or_role:sorciere",
                "text": "La Sorcière frémit en scrutant ses potions à la lueur de la lune…"})

    if sorciere.is_human and state.mode == "player":
        extra = {
            "victim": victim.name if victim else None,
            "heal_available": heal_available,
            "kill_available": kill_available,
        }
        candidates_kill = [p for p in state.alive_players() if p.id != sorciere.id]
        result = state.await_human_action("witch_action", candidates_kill, extra=extra)
        action = result.get("extra", {}).get("action") if result else "pass"
        kill_target_id = result.get("target_id") if result and action == "kill" else None

        if action == "heal" and heal_available and victim:
            sorciere.witch_heal_used = True
            state.night_actions["witch_saved"] = True
            state.emit({"type": "narration", "visible": "spectator_or_role:sorciere",
                        "text": f"La Sorcière verse la potion de vie sur {victim.name}."})

        elif action == "kill" and kill_available and kill_target_id:
            sorciere.witch_kill_used = True
            state.night_actions["witch_kill"] = kill_target_id
            target = state.get_player(kill_target_id)
            state.emit({"type": "narration", "visible": "spectator_or_role:sorciere",
                        "text": f"La Sorcière répand son poison sur {target.name if target else '?'}."})
    else:
        alive_names = _names(state.alive_players())
        mem = state.npc_memories.get(sorciere.id)
        sus = mem.suspicions if mem else {}
        decision = ai.witch_ai_decision(
            victim.name if victim else "", heal_available, kill_available, alive_names, sus
        )
        if decision["heal"] and victim:
            sorciere.witch_heal_used = True
            state.night_actions["witch_saved"] = True
            state.emit({"type": "narration", "visible": "spectator",
                        "text": f"La Sorcière sauve secrètement {victim.name}."})
        if decision["kill_target"]:
            sorciere.witch_kill_used = True
            kill_p = next((p for p in state.alive_players() if p.name == decision["kill_target"]), None)
            if kill_p:
                state.night_actions["witch_kill"] = kill_p.id
                state.emit({"type": "narration", "visible": "spectator",
                            "text": f"La Sorcière empoisonne {kill_p.name}."})


# ---------------------------------------------------------------------------
# Phase JOUR
# ---------------------------------------------------------------------------

def run_jour(state: "GameState"):
    state.phase = "jour"
    alive = state.alive_players()
    dead = [p for p in state.players if not p.is_alive]

    # Narration ouverture du jour
    victim_id = state.night_actions.get("loup_victim")
    victim_saved = state.night_actions.get("witch_saved", False)
    witch_kill_id = state.night_actions.get("witch_kill")

    victims_this_night = []
    if victim_id and not victim_saved:
        v = state.get_player(victim_id)
        if v:
            victims_this_night.append(v.name)
    if witch_kill_id:
        v2 = state.get_player(witch_kill_id)
        if v2:
            victims_this_night.append(v2.name)

    if victims_this_night:
        desc = f"Matin du jour {state.round}. Le village découvre les corps de {', '.join(victims_this_night)}."
    elif victim_saved:
        v = state.get_player(victim_id) if victim_id else None
        desc = f"Matin du jour {state.round}. Miracle : {v.name if v else 'quelqu\'un'} a survécu cette nuit."
    else:
        desc = f"Matin du jour {state.round}. Le village se réveille, épargné cette nuit."

    narration = ai.narrate(desc, event_log=state.event_log)
    state.emit({"type": "narration", "text": narration})

    # --- Discussion : passe 1 (ouverture) ---
    _passes = int(cfg.get("DISCUSSION_PASSES"))
    _discussion_round(state, passes=_passes)

    # Tour de parole humain
    human = state.get_human()
    if human and human.is_alive and state.mode == "player":
        result = state.await_human_action("chat", [], extra={"timeout": int(cfg.get("HUMAN_CHAT_TIMEOUT_1"))})
        human_msg = result.get("extra", {}).get("message", "") if result else ""
    else:
        human_msg = ""

    # --- Discussion : passe 2 (réactions au joueur ou débat libre) ---
    _discussion_round(state, passes=_passes, human_last_message=human_msg or None)

    # Deuxième tour de parole humain (réponse aux réactions)
    if human and human.is_alive and state.mode == "player":
        result = state.await_human_action("chat", [], extra={"timeout": int(cfg.get("HUMAN_CHAT_TIMEOUT_2"))})
        human_msg2 = result.get("extra", {}).get("message", "") if result else ""
        if human_msg2:
            _discussion_round(state, passes=_passes, human_last_message=human_msg2)

    # --- Vote ---
    _run_vote(state)


def _dead_events(state: "GameState") -> list[str]:
    """Construit la liste des morts avec cause depuis l'event_log."""
    _cause_labels = {
        "loup":     "tué par les loups",
        "vote":     "éliminé par vote du village",
        "sorciere": "empoisonné par la sorcière",
        "chasseur": "abattu par le chasseur",
        "chagrin":  "mort de chagrin (amoureux)",
    }
    events = []
    for evt in state.event_log:
        if evt.get("type") != "death":
            continue
        name = evt.get("name", "?")
        cause = _cause_labels.get(evt.get("cause", ""), evt.get("cause", ""))
        role = evt.get("role_revealed", "")
        entry = f"{name} ({cause})" + (f", rôle révélé : {role}" if role else "")
        if entry not in events:
            events.append(entry)
    return events


def _sus_alive(mem, state: "GameState") -> dict[str, float]:
    """Suspicions filtrées aux joueurs encore vivants (par nom)."""
    result = {}
    for pid, score in mem.suspicions.items():
        p = state.get_player(pid)
        if p is not None and p.is_alive:
            result[p.name] = score
    return result


def _npc_vote_target(mem, candidates: list) -> "Player | None":
    """Vote déterministe : candidat vivant avec le score de suspicion le plus élevé.
    Légère gigue aléatoire pour éviter les ex-æquo mécaniques."""
    if not candidates:
        return None
    scored = [
        (p, (mem.suspicions.get(p.id, 0.3) if mem else 0.3) + random.uniform(-0.05, 0.05))
        for p in candidates
    ]
    return max(scored, key=lambda x: x[1])[0]


def _discussion_round(state: "GameState", passes: int = 2,
                      human_last_message: str | None = None):
    alive_npcs = [p for p in state.alive_players() if not p.is_human]
    random.shuffle(alive_npcs)

    dead_evts = _dead_events(state)
    human = state.get_human()
    human_name = human.name if human and human.is_alive else None

    for _ in range(passes):
        for npc in alive_npcs:
            mem = state.npc_memories.setdefault(npc.id, NPCMemory())
            sus_by_name = _sus_alive(mem, state)
            victim_id = state.night_actions.get("loup_victim")
            victim = state.get_player(victim_id) if victim_id else None
            last_victim_name = victim.name if (victim and not victim.is_alive) else None

            speech = ai.npc_dialogue(
                npc_name=npc.name,
                npc_role_cover="villageois",
                suspicions=sus_by_name,
                recent_speech=mem.recent_speech,
                alive_names=_names(state.alive_players()),
                dead_events=dead_evts,
                last_victim=last_victim_name,
                human_last_message=human_last_message,
                round_num=state.round,
                human_name=human_name,
                event_log=state.event_log,
                is_wolf=(npc.role == "loup-garou"),
            )
            state.tts_ack_event.clear()
            state.emit({"type": "npc_dialogue", "speaker": npc.name,
                        "player_id": npc.id, "text": speech})
            mem.recent_speech.append(f"{npc.name}: {speech}")
            if len(mem.recent_speech) > 8:
                mem.recent_speech = mem.recent_speech[-8:]
            state.tts_ack_event.wait(timeout=int(cfg.get("TTS_ACK_TIMEOUT")))


def _run_vote(state: "GameState"):
    state.phase = "vote"
    alive = state.alive_players()
    votes: dict[str, str] = {}  # voter_id -> target_id

    state.emit({"type": "narration",
                "text": "Le village se rassemble. Il est temps de voter pour éliminer un suspect."})

    # Vote humain
    human = state.get_human()
    if human and human.is_alive and state.mode == "player":
        candidates = [p for p in alive if p.id != human.id]
        result = state.await_human_action("vote", candidates)
        if result:
            votes[human.id] = result["target_id"]

    # Votes IA — raisonnement IA sur l'état du jeu, fallback suspicion si non parsable
    dead_evts = _dead_events(state)

    # Discussion récente : dernières répliques de tous les PNJ vivants
    all_recent: list[str] = []
    seen_lines: set[str] = set()
    for p in alive:
        if not p.is_human:
            m = state.npc_memories.get(p.id)
            if m:
                for line in m.recent_speech[-2:]:
                    if line not in seen_lines:
                        seen_lines.add(line)
                        all_recent.append(line)

    for npc in alive:
        if npc.is_human:
            continue
        mem = state.npc_memories.get(npc.id)
        candidates_list = [p for p in alive if p.id != npc.id]
        candidates_names = [p.name for p in candidates_list]

        ally_names = (
            [p.name for p in alive if p.team == "loups" and p.id != npc.id]
            if npc.team == "loups" else []
        )

        chosen_name = ai.npc_vote(
            npc_name=npc.name,
            npc_role=npc.role,
            ally_names=ally_names,
            candidates=candidates_names,
            dead_events=dead_evts,
            recent_discussion=all_recent,
            round_num=state.round,
            event_log=state.event_log,
            is_wolf=(npc.team == "loups"),
        )

        chosen = next((p for p in candidates_list if p.name == chosen_name), None)
        if not chosen:
            chosen = _npc_vote_target(mem, candidates_list)
        if chosen:
            votes[npc.id] = chosen.id

    # Décompte
    tally: dict[str, int] = {}
    for target_id in votes.values():
        tally[target_id] = tally.get(target_id, 0) + 1

    if not tally:
        state.emit({"type": "narration", "text": "Personne n'a pu se mettre d'accord. Aucun vote cette fois."})
        run_night(state)
        return

    max_votes = max(tally.values())
    most_voted = [pid for pid, count in tally.items() if count == max_votes]
    eliminated_id = random.choice(most_voted)
    eliminated = state.get_player(eliminated_id)

    # Qui a voté pour l'éliminé ?
    voters_for = [vid for vid, tid in votes.items() if tid == eliminated_id]

    vote_summary = ", ".join(
        f"{state.get_player(vid).name} → {state.get_player(tid).name}"
        for vid, tid in votes.items()
        if state.get_player(vid) and state.get_player(tid)
    )
    state.emit({"type": "vote_result", "text": f"Résultat des votes : {vote_summary}"})

    if eliminated:
        eliminated.is_alive = False
        narration = ai.narrate(
            f"{eliminated.name} est éliminé·e par le vote du village avec {max_votes} voix. "
            f"Son rôle était : {eliminated.role}.",
            event_log=state.event_log,
        )
        state.emit({"type": "death", "player_id": eliminated.id, "name": eliminated.name,
                    "cause": "vote", "role_revealed": eliminated.role, "text": narration})
        state.emit({"type": "narration", "text": narration})

        # Réaction si chasseur éliminé par vote
        if eliminated.role == "chasseur":
            _chasseur_retaliation(state, eliminated)

        _update_suspicions_after_vote(state, eliminated, voters_for)

    winner = state.check_win()
    if winner:
        _end_game(state, winner)
        return

    state.round += 1
    run_night(state)


# ---------------------------------------------------------------------------
# Fin de partie
# ---------------------------------------------------------------------------

def _end_game(state: "GameState", winner: str):
    state.phase = "game_over"
    state.winner = winner

    conclusion = WIN_CONDITIONS.get(winner, "La partie est terminée.")
    narration = ai.narrate(conclusion, event_log=state.event_log)
    state.emit({"type": "game_over", "winner": winner, "text": narration})
