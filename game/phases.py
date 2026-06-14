from __future__ import annotations
import random
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from game import ai_director as ai
from game import config as cfg
from game.roles import NIGHT_ORDER, WIN_CONDITIONS
from game.state import NPCMemory

_executor = ThreadPoolExecutor(max_workers=1)

if TYPE_CHECKING:
    from game.state import GameState, Player


def _names(players: list) -> list[str]:
    return [p.name for p in players]


def _kill_player(state: "GameState", player: "Player", cause: str = "mafia"):
    player.is_alive = False
    state.emit({"type": "death", "player_id": player.id, "name": player.name, "cause": cause,
                "text": f"{player.name} was killed tonight."})


def _update_suspicions_after_vote(state: "GameState", eliminated: "Player", voters_for: list[str]):
    for npc_id, mem in state.npc_memories.items():
        if eliminated.team == "mafia":
            for m in state.alive_mafia():
                mem.suspicions[m.id] = min(1.0, mem.suspicions.get(m.id, 0) + 0.3)
        else:
            for voter_id in voters_for:
                mem.suspicions[voter_id] = min(1.0, mem.suspicions.get(voter_id, 0) + 0.15)


# ---------------------------------------------------------------------------
# Night phase
# ---------------------------------------------------------------------------

def run_night(state: "GameState"):
    state.phase = "night"
    alive = state.alive_players()

    narration = ai.narrate(
        f"Night {state.round} falls over the town. The residents go to sleep, uneasy. "
        f"{len(alive)} players remain.",
        event_log=state.event_log,
    )
    state.emit({"type": "narration", "text": narration})

    state.night_actions = {}

    for role in NIGHT_ORDER:
        actors = [p for p in state.alive_players() if p.role == role]
        if not actors:
            continue

        if role == "mafia":
            _night_mafia(state)
        elif role == "doctor":
            _night_doctor(state, actors[0])
        elif role == "sheriff":
            _night_sheriff(state, actors[0])
        elif role == "vigilante":
            _night_vigilante(state, actors[0])

    victim_id = state.night_actions.get("mafia_victim")
    doctor_saved = state.night_actions.get("doctor_saved", False)
    vigilante_kill_id = state.night_actions.get("vigilante_kill")

    if victim_id and not doctor_saved:
        victim = state.get_player(victim_id)
        if victim and victim.is_alive:
            _kill_player(state, victim, cause="mafia")

    if vigilante_kill_id:
        target = state.get_player(vigilante_kill_id)
        if target and target.is_alive:
            _kill_player(state, target, cause="vigilante")
            if target.team != "mafia":
                state.emit({"type": "narration",
                            "text": "The vigilante shot an innocent. Overcome with guilt, they take their own life."})
                vig = next((p for p in state.alive_players() if p.role == "vigilante"), None)
                if vig:
                    _kill_player(state, vig, cause="guilt")

    winner = state.check_win()
    if winner:
        _end_game(state, winner)
        return

    run_day(state)


def _night_mafia(state: "GameState"):
    mafia = state.alive_mafia()
    candidates = [p for p in state.alive_players() if p.team != "mafia"]
    if not candidates:
        return

    human_mafia = next((p for p in mafia if p.is_human), None)
    mafia_names = _names(mafia)
    candidate_names = _names(candidates)

    human = state.get_human()
    human_hears_mafia = state.mode == "spectator" or (human and human.team == "mafia")

    for member in mafia:
        if not member.is_human:
            speech = ai.mafia_deliberation(member.name, mafia_names, candidate_names, state.round,
                                           event_log=state.event_log, personality=member.personality)
            if human_hears_mafia:
                state.tts_ack_event.clear()
            state.emit({"type": "mafia_private", "visible": "mafia",
                        "speaker": member.name, "text": speech})
            if human_hears_mafia:
                state.tts_ack_event.wait(timeout=int(cfg.get("TTS_ACK_TIMEOUT")))

    if human_mafia and state.mode == "player":
        result = state.await_human_action("mafia_vote", candidates)
        victim_id = result["target_id"] if result else random.choice(candidates).id
    else:
        mem = state.npc_memories.get(mafia[0].id) if mafia else None
        chosen = _npc_vote_target(mem, candidates)
        victim_id = chosen.id if chosen else random.choice(candidates).id

    state.night_actions["mafia_victim"] = victim_id
    victim = state.get_player(victim_id)
    state.emit({"type": "mafia_private", "visible": "mafia",
                "text": f"The mafia has chosen {victim.name if victim else '?'}."})


def _night_doctor(state: "GameState", doctor: "Player"):
    candidates = [p for p in state.alive_players() if p.id != state.doctor_last_save_id]
    if not candidates:
        candidates = state.alive_players()

    state.emit({"type": "narration", "visible": "spectator_or_role:doctor",
                "text": "The Doctor quietly makes their rounds, ready to save a life…"})

    if doctor.is_human and state.mode == "player":
        result = state.await_human_action("doctor_save", candidates)
        save_id = result["target_id"] if result else random.choice(candidates).id
    else:
        decision = ai.doctor_ai_decision(_names(candidates))
        if decision["save_target"]:
            p = next((x for x in candidates if x.name == decision["save_target"]), None)
            save_id = p.id if p else random.choice(candidates).id
        else:
            save_id = random.choice(candidates).id

    saved = state.get_player(save_id)
    if not saved:
        return

    state.doctor_last_save_id = save_id
    if not doctor.is_human:
        mem_doc = state.npc_memories.setdefault(doctor.id, NPCMemory())
        mem_doc.saves.append(saved.name)

    victim_id = state.night_actions.get("mafia_victim")
    if victim_id and victim_id == save_id:
        state.night_actions["doctor_saved"] = True
        state.emit({"type": "narration", "visible": "spectator_or_role:doctor",
                    "text": f"The Doctor rushes to save {saved.name} just in time."})
    else:
        state.emit({"type": "narration", "visible": "spectator",
                    "text": f"The Doctor protected {saved.name} tonight."})


def _night_sheriff(state: "GameState", sheriff: "Player"):
    candidates = [p for p in state.alive_players() if p.id != sheriff.id]
    if not candidates:
        return

    state.emit({"type": "narration", "visible": "spectator_or_role:sheriff",
                "text": "The Sheriff opens their badge and begins their investigation…"})

    if sheriff.is_human and state.mode == "player":
        result = state.await_human_action("sheriff_investigate", candidates)
        target_id = result["target_id"] if result else random.choice(candidates).id
    else:
        mem = state.npc_memories.setdefault(sheriff.id, NPCMemory())
        # Prefer players not yet investigated; fall back to full candidates list
        investigated_names = set(mem.investigations.keys())
        pool = [p for p in candidates if p.name not in investigated_names] or candidates
        # Among the pool, investigate the most suspicious first
        if mem.suspicions:
            best = max(
                [(p, mem.suspicions.get(p.id, 0.3) + random.uniform(-0.05, 0.05)) for p in pool],
                key=lambda x: x[1],
            )
            target_id = best[0].id
        else:
            target_id = random.choice(pool).id

    target = state.get_player(target_id)
    if not target:
        return

    result_text = "Mafia" if target.team == "mafia" else "Innocent"

    if sheriff.is_human and state.mode == "player":
        state.emit({"type": "role_reveal", "visible": "human",
                    "target_name": target.name, "role": result_text,
                    "text": f"[Sheriff] {target.name} is: {result_text}."})
    else:
        mem = state.npc_memories.setdefault(sheriff.id, NPCMemory())
        mem.investigations[target.name] = result_text
        mem.known_role = f"{target.name} is {result_text}"
        if target.team == "mafia":
            mem.suspicions[target.id] = 1.0
        else:
            # Clear suspicion on confirmed innocents
            mem.suspicions[target.id] = min(mem.suspicions.get(target.id, 0.0), 0.0)

    state.emit({"type": "role_reveal", "visible": "spectator",
                "target_name": target.name, "role": result_text,
                "text": f"[Spectator] The Sheriff learns that {target.name} is {result_text}."})


def _night_vigilante(state: "GameState", vigilante: "Player"):
    if vigilante.vigilante_shot_used:
        return

    candidates = [p for p in state.alive_players() if p.id != vigilante.id]
    if not candidates:
        return

    state.emit({"type": "narration", "visible": "spectator_or_role:vigilante",
                "text": "The Vigilante grips their weapon, watching the dark streets…"})

    if vigilante.is_human and state.mode == "player":
        result = state.await_human_action("vigilante_shoot", candidates,
                                          extra={"message": "Use your one shot, or skip?"})
        if result and result.get("target_id"):
            vigilante.vigilante_shot_used = True
            state.night_actions["vigilante_kill"] = result["target_id"]
    else:
        mem = state.npc_memories.get(vigilante.id)
        sus = _sus_alive(mem, state) if mem else {}
        decision = ai.vigilante_ai_decision(_names(candidates), sus)
        if decision["shoot_target"]:
            p = next((x for x in candidates if x.name == decision["shoot_target"]), None)
            if p:
                vigilante.vigilante_shot_used = True
                state.night_actions["vigilante_kill"] = p.id


# ---------------------------------------------------------------------------
# Day phase
# ---------------------------------------------------------------------------

def run_day(state: "GameState"):
    state.phase = "day"

    victim_id = state.night_actions.get("mafia_victim")
    victim_saved = state.night_actions.get("doctor_saved", False)
    vigilante_kill_id = state.night_actions.get("vigilante_kill")

    victims_this_night = []
    if victim_id and not victim_saved:
        v = state.get_player(victim_id)
        if v:
            victims_this_night.append(v.name)
    if vigilante_kill_id:
        v2 = state.get_player(vigilante_kill_id)
        if v2 and not v2.is_alive:
            victims_this_night.append(v2.name)

    if victims_this_night:
        desc = f"Day {state.round}. The town wakes to find {', '.join(victims_this_night)} dead."
    elif victim_saved:
        v = state.get_player(victim_id) if victim_id else None
        desc = f"Day {state.round}. Miraculously, {v.name if v else 'someone'} survived the night."
    else:
        desc = f"Day {state.round}. The town wakes up safe — no one died last night."

    narration = ai.narrate(desc, event_log=state.event_log)
    state.emit({"type": "narration", "text": narration})

    _discussion_round(state, passes=1)

    human = state.get_human()
    if human and human.is_alive and state.mode == "player":
        result = state.await_human_action("chat", [], extra={"timeout": int(cfg.get("HUMAN_CHAT_TIMEOUT_1"))})
        human_msg = result.get("extra", {}).get("message", "") if result else ""
        if human_msg:
            _reaction_round(state, human_msg)

    _run_vote_sequential(state)


def _dead_events(state: "GameState") -> list[str]:
    _cause_labels = {
        "mafia":      "killed by the mafia",
        "vote":       "voted out",
        "vigilante":  "shot by the vigilante",
        "guilt":      "died of guilt (vigilante)",
    }
    events = []
    for evt in state.event_log:
        if evt.get("type") != "death":
            continue
        name = evt.get("name", "?")
        cause = _cause_labels.get(evt.get("cause", ""), evt.get("cause", ""))
        role = evt.get("role_revealed", "")
        entry = f"{name} ({cause})" + (f", role revealed: {role}" if role else "")
        if entry not in events:
            events.append(entry)
    return events


def _sus_alive(mem, state: "GameState") -> dict[str, float]:
    result = {}
    for pid, score in mem.suspicions.items():
        p = state.get_player(pid)
        if p is not None and p.is_alive:
            result[p.name] = score
    return result


def _npc_private_context(npc: "Player", state: "GameState") -> str:
    """Return a private role-awareness block injected into NPC prompts."""
    mem = state.npc_memories.get(npc.id)

    if npc.role == "sheriff":
        if mem and mem.investigations:
            findings = "; ".join(f"{name}: {res}" for name, res in mem.investigations.items())
            return (
                f"SECRET ROLE — SHERIFF: your private investigation results so far: [{findings}]. "
                "Use this intel to guide the town toward confirmed mafia members. "
                "You may reveal your role and findings openly, or steer suspicion subtly to protect yourself — be strategic."
            )
        return (
            "SECRET ROLE — SHERIFF: you haven't investigated anyone yet. "
            "Act like a villager for now, but pay close attention to behaviour."
        )

    if npc.role == "doctor":
        if mem and mem.saves:
            saved_list = ", ".join(mem.saves[-4:])
            return (
                f"SECRET ROLE — DOCTOR: you have protected these players on previous nights: [{saved_list}]. "
                "Keep your identity secret to stay alive — a dead doctor can't save anyone. "
                "Don't reveal yourself unless the town is about to vote out someone you know is innocent."
            )
        return (
            "SECRET ROLE — DOCTOR: you haven't saved anyone yet. "
            "Act like a villager. Protect your identity — you are most valuable alive."
        )

    if npc.role == "vigilante":
        if npc.vigilante_shot_used:
            return (
                "SECRET ROLE — VIGILANTE: you have already used your one shot. "
                "Stay quiet about it — you are now a regular voter. Help the town with your reasoning."
            )
        return (
            "SECRET ROLE — VIGILANTE: you have one shot remaining, usable at night. "
            "Keep your identity secret. Don't reveal yourself prematurely; act like a villager "
            "until you have near-certain evidence of a mafia member."
        )

    if npc.role == "jester":
        return (
            "SECRET ROLE — JESTER: your ONLY win condition is to be VOTED OUT by the town. "
            "You must make the town want to eliminate you. "
            "Say contradictory things, make wild or poorly-reasoned accusations, act evasive or defensive when questioned. "
            "Be subtly suspicious — not so blatant that people think you're the jester, "
            "but suspicious enough that they decide to vote you out. "
            "Never admit you are the jester."
        )

    return ""


def _npc_vote_target(mem, candidates: list) -> "Player | None":
    if not candidates:
        return None
    scored = [
        (p, (mem.suspicions.get(p.id, 0.3) if mem else 0.3) + random.uniform(-0.05, 0.05))
        for p in candidates
    ]
    return max(scored, key=lambda x: x[1])[0]


def _reaction_round(state: "GameState", human_msg: str):
    alive_npcs = [p for p in state.alive_players() if not p.is_human]
    if not alive_npcs:
        return
    reactors = random.sample(alive_npcs, min(2, len(alive_npcs)))
    _discussion_round(state, passes=1, human_last_message=human_msg, npc_subset=reactors)


def _discussion_round(state: "GameState", passes: int = 1,
                      human_last_message: str | None = None,
                      npc_subset: list | None = None):
    alive_npcs = npc_subset if npc_subset is not None else [p for p in state.alive_players() if not p.is_human]
    random.shuffle(alive_npcs)
    if not alive_npcs:
        return

    dead_evts = _dead_events(state)
    human = state.get_human()
    human_name = human.name if human and human.is_alive else None
    victim_id = state.night_actions.get("mafia_victim")
    victim = state.get_player(victim_id) if victim_id else None
    last_victim_name = victim.name if (victim and not victim.is_alive) else None

    def _gen(npc):
        mem = state.npc_memories.setdefault(npc.id, NPCMemory())
        return ai.npc_dialogue(
            npc_name=npc.name,
            npc_role_cover="villager",
            suspicions=_sus_alive(mem, state),
            recent_speech=list(mem.recent_speech),
            alive_names=_names(state.alive_players()),
            dead_events=dead_evts,
            last_victim=last_victim_name,
            human_last_message=human_last_message,
            round_num=state.round,
            human_name=human_name,
            event_log=state.event_log,
            is_mafia=(npc.role == "mafia"),
            personality=npc.personality,
            private_context=_npc_private_context(npc, state),
        )

    for _ in range(passes):
        current = _gen(alive_npcs[0])
        for i, npc in enumerate(alive_npcs):
            next_future = (
                _executor.submit(_gen, alive_npcs[i + 1])
                if i + 1 < len(alive_npcs) else None
            )
            mem = state.npc_memories.setdefault(npc.id, NPCMemory())
            state.tts_ack_event.clear()
            state.emit({"type": "npc_dialogue", "speaker": npc.name,
                        "player_id": npc.id, "text": current})
            mem.recent_speech.append(f"{npc.name}: {current}")
            if len(mem.recent_speech) > 8:
                mem.recent_speech = mem.recent_speech[-8:]
            state.tts_ack_event.wait(timeout=int(cfg.get("TTS_ACK_TIMEOUT")))
            if next_future:
                current = next_future.result()


def _run_vote_sequential(state: "GameState"):
    state.phase = "vote"
    alive = state.alive_players()
    votes: dict[str, str] = {}

    state.emit({"type": "narration",
                "text": "The town gathers. Everyone will speak before casting their vote."})

    dead_evts = _dead_events(state)
    npc_voters = [p for p in alive if not p.is_human]

    def _gen_vote(npc):
        candidates_list = [p for p in alive if p.id != npc.id]
        mem = state.npc_memories.get(npc.id)
        return ai.npc_vote_aloud(
            npc_name=npc.name,
            npc_role=npc.role,
            ally_names=[p.name for p in alive if p.team == "mafia" and p.id != npc.id]
                       if npc.team == "mafia" else [],
            candidates=[p.name for p in candidates_list],
            dead_events=dead_evts,
            round_num=state.round,
            event_log=state.event_log,
            is_mafia=(npc.team == "mafia"),
            personality=npc.personality,
            private_context=_npc_private_context(npc, state),
        )

    _ABSTAIN_KEYWORDS = ("i abstain", "abstain", "i pass", "pass my vote", "no vote")

    if npc_voters:
        current = _gen_vote(npc_voters[0])
        for i, npc in enumerate(npc_voters):
            next_future = (
                _executor.submit(_gen_vote, npc_voters[i + 1])
                if i + 1 < len(npc_voters) else None
            )

            statement = current
            candidates_list = [p for p in alive if p.id != npc.id]

            abstaining = any(kw in statement.lower() for kw in _ABSTAIN_KEYWORDS)
            if not abstaining:
                voted = next(
                    (p for p in candidates_list if p.name.lower() in statement.lower()),
                    None,
                )
                if not voted:
                    voted = _npc_vote_target(state.npc_memories.get(npc.id), candidates_list)
                if voted:
                    votes[npc.id] = voted.id

            mem = state.npc_memories.get(npc.id)
            state.tts_ack_event.clear()
            state.emit({"type": "npc_dialogue", "speaker": npc.name,
                        "player_id": npc.id, "text": statement})
            if mem:
                mem.recent_speech.append(f"{npc.name}: {statement}")
                if len(mem.recent_speech) > 8:
                    mem.recent_speech = mem.recent_speech[-8:]
            state.tts_ack_event.wait(timeout=int(cfg.get("TTS_ACK_TIMEOUT")))

            if next_future:
                current = next_future.result()

    human = state.get_human()
    if human and human.is_alive and state.mode == "player":
        # Human speaks before casting their vote
        result_chat = state.await_human_action(
            "chat", [],
            extra={"timeout": int(cfg.get("HUMAN_CHAT_TIMEOUT_1"))},
        )
        human_msg = result_chat.get("extra", {}).get("message", "") if result_chat else ""
        if human_msg:
            _reaction_round(state, human_msg)

        # Human casts their vote (empty target_id = abstain)
        candidates = [p for p in state.alive_players() if p.id != human.id]
        result = state.await_human_action("vote", candidates)
        if result and result.get("target_id"):
            votes[human.id] = result["target_id"]

    tally: dict[str, int] = {}
    for target_id in votes.values():
        tally[target_id] = tally.get(target_id, 0) + 1

    total_voters = len(alive)  # all alive players, abstentions count against the target
    max_votes = max(tally.values()) if tally else 0

    if max_votes * 2 <= total_voters:
        state.emit({"type": "narration",
                    "text": "No strict majority reached. Nobody is eliminated this round."})
        state.round += 1
        run_night(state)
        return

    eliminated_id = max(tally, key=tally.get)
    eliminated = state.get_player(eliminated_id)
    voters_for = [vid for vid, tid in votes.items() if tid == eliminated_id]

    vote_summary = ", ".join(
        f"{state.get_player(vid).name} → {state.get_player(tid).name}"
        for vid, tid in votes.items()
        if state.get_player(vid) and state.get_player(tid)
    )
    state.emit({"type": "vote_result", "text": f"Results: {vote_summary}"})

    if eliminated:
        eliminated.is_alive = False

        if eliminated.role == "jester":
            narration = ai.narrate(
                f"{eliminated.name} is voted out with {max_votes} votes. "
                f"Their role was: {eliminated.role}. The Jester wins!",
                event_log=state.event_log,
            )
            state.emit({"type": "death", "player_id": eliminated.id, "name": eliminated.name,
                        "cause": "vote", "role_revealed": eliminated.role, "text": narration})
            _end_game(state, "jester")
            return

        narration = ai.narrate(
            f"{eliminated.name} is voted out with {max_votes} votes. "
            f"Their role was: {eliminated.role}.",
            event_log=state.event_log,
        )
        state.emit({"type": "death", "player_id": eliminated.id, "name": eliminated.name,
                    "cause": "vote", "role_revealed": eliminated.role, "text": narration})

        _update_suspicions_after_vote(state, eliminated, voters_for)

    winner = state.check_win()
    if winner:
        _end_game(state, winner)
        return

    state.round += 1
    run_night(state)


# ---------------------------------------------------------------------------
# End of game
# ---------------------------------------------------------------------------

def _end_game(state: "GameState", winner: str):
    state.phase = "game_over"
    state.winner = winner

    conclusion = WIN_CONDITIONS.get(winner, "The game is over.")
    narration = ai.narrate(conclusion, event_log=state.event_log)
    state.emit({"type": "game_over", "winner": winner, "text": narration})
