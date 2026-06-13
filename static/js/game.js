// ============================================================
// game.js — Consommateur SSE + rendu de l'interface
// ============================================================

let gameMode = 'player';
let gameStarted = false;
let sseSource = null;
let sseCursor = 0;
let humanPlayerId = null;
let allPlayers = [];  // { id, name, is_human }

// -------- Utilitaires ---------

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function setMode(mode) {
  gameMode = mode;
  document.getElementById('btn-mode-player').classList.toggle('active', mode === 'player');
  document.getElementById('btn-mode-spectator').classList.toggle('active', mode === 'spectator');
  document.getElementById('player-fields').style.display = mode === 'player' ? 'flex' : 'none';
  document.getElementById('player-fields').style.flexDirection = 'column';
}

// -------- Démarrage ----------

async function startGame() {
  const playerName = document.getElementById('input-name').value.trim() || 'Joueur';
  const roleChoice = document.getElementById('input-role').value;
  const playerCount = parseInt(document.getElementById('input-count').value);

  const btn = document.getElementById('btn-start');
  btn.disabled = true;
  btn.textContent = 'Démarrage…';

  try {
    const res = await fetch('/api/game/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        player_name: playerName,
        role_choice: roleChoice === 'random' ? 'random' : roleChoice,
        player_count: playerCount,
        mode: gameMode,
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Erreur');

    allPlayers = data.players;
    humanPlayerId = data.mode === 'player' ? 'human' : null;

    // Assigner les voix distinctes
    const npcPlayers = data.players.filter(p => !p.is_human);
    TTS.assignVoices(npcPlayers);

    // Afficher rôle dans le header
    if (data.your_role) {
      document.getElementById('header-role').textContent =
        `${data.your_role_emoji} ${data.your_name} — ${data.your_role_label}`;
    } else {
      document.getElementById('header-role').textContent = '👁 Mode Spectateur';
    }

    _renderPlayerList(data.players, []);
    showScreen('game-screen');
    _startSSE();

  } catch (e) {
    alert('Erreur au démarrage : ' + e.message);
    btn.disabled = false;
    btn.textContent = 'Commencer la partie';
  }
}

// -------- SSE ---------

function _startSSE() {
  if (sseSource) sseSource.close();
  sseSource = new EventSource(`/api/events?cursor=${sseCursor}`);

  sseSource.onmessage = (e) => {
    const evt = JSON.parse(e.data);
    sseCursor++;
    _handleEvent(evt);
  };

  sseSource.onerror = () => {
    // Reconnexion automatique après 2s
    sseSource.close();
    setTimeout(_startSSE, 2000);
  };
}

// -------- Gestion des événements --------

function _handleEvent(evt) {
  switch (evt.type) {
    case 'narration':
      _appendLog(evt.text, 'narration');
      TTS.speakNarration(evt.text);
      _setTyping(false);
      break;

    case 'npc_dialogue':
      _appendLog(`<span class="speaker">${evt.speaker}</span> : ${evt.text}`, 'npc');
      TTS.speakNPC(evt.text, evt.player_id, evt.speaker);
      break;

    case 'wolf_private':
      if (evt.speaker) {
        _appendLog(`🐺 <span class="speaker">${evt.speaker}</span> (loups) : ${evt.text}`, 'wolf-private');
        TTS.speakWolf(evt.text, evt.player_id || 'wolf');
      } else {
        _appendLog(`🐺 ${evt.text}`, 'wolf-private');
      }
      break;

    case 'role_reveal':
      _appendLog(`🔮 ${evt.text}`, 'secret');
      TTS.speakSecret(evt.text);
      break;

    case 'lovers_set':
    case 'lover_reveal':
      _appendLog(`💘 ${evt.text}`, 'secret');
      TTS.speakSecret(evt.text);
      break;

    case 'death':
      _appendLog(`💀 ${evt.text}`, 'death');
      TTS.speakNarration(evt.text);
      _markDead(evt.player_id, evt.name, evt.role_revealed);
      break;

    case 'vote_result':
      _appendLog(evt.text, 'vote');
      break;

    case 'awaiting_action':
      _setTyping(false);
      _renderActionPanel(evt.action);
      break;

    case 'game_over':
      _setTyping(false);
      _renderGameOver(evt.winner, evt.text);
      TTS.speakNarration(evt.text);
      break;

    case 'error':
      _appendLog(`⚠️ ${evt.text}`, 'system');
      break;

    case 'no_game':
      break;

    default:
      if (evt.text) _appendLog(evt.text, 'system');
  }

  // Mise à jour du header de phase
  if (evt.phase) _updatePhaseHeader(evt.phase, evt.round);
}

// -------- Log ---------

function _appendLog(html, cssClass) {
  const log = document.getElementById('event-log');
  const div = document.createElement('div');
  div.className = `log-entry ${cssClass}`;
  div.innerHTML = html;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function _setTyping(visible) {
  const el = document.getElementById('typing-indicator');
  el.classList.toggle('hidden', !visible);
}

// -------- Players sidebar ---------

function _renderPlayerList(players, deadIds) {
  const aliveUl = document.getElementById('alive-list');
  const deadUl = document.getElementById('dead-list');
  aliveUl.innerHTML = '';
  deadUl.innerHTML = '';

  players.forEach(p => {
    const li = document.createElement('li');
    li.id = `player-li-${p.id}`;
    li.textContent = p.is_human ? `${p.name} (vous)` : p.name;
    if (p.is_human) li.classList.add('human');
    aliveUl.appendChild(li);
  });
}

function _markDead(playerId, name, roleRevealed) {
  const li = document.getElementById(`player-li-${playerId}`);
  if (!li) {
    // Créer dans la liste des morts
    const deadUl = document.getElementById('dead-list');
    const newLi = document.createElement('li');
    newLi.id = `player-li-${playerId}`;
    newLi.innerHTML = name + (roleRevealed ? `<small>${roleRevealed}</small>` : '');
    deadUl.appendChild(newLi);
    return;
  }
  // Déplacer vers morts
  const deadUl = document.getElementById('dead-list');
  const newLi = document.createElement('li');
  newLi.id = `player-li-dead-${playerId}`;
  newLi.innerHTML = name + (roleRevealed ? `<small>${roleRevealed}</small>` : '');
  deadUl.appendChild(newLi);
  li.remove();
}

function _updatePhaseHeader(phase, round) {
  const phaseLabels = {
    nuit: '🌙 Nuit',
    jour: '☀️ Jour',
    vote: '🗳 Vote',
    game_over: '🏁 Fin',
  };
  const label = phaseLabels[phase] || phase;
  const r = round || '';
  document.getElementById('header-phase').textContent = `${label} ${r}`.trim();
}

// -------- Panneau d'action --------

function _renderActionPanel(action) {
  const panel = document.getElementById('action-panel');
  panel.classList.remove('hidden');
  panel.innerHTML = '';

  switch (action.type) {
    case 'wolf_vote':
      _renderVotePanel(panel, action, 'wolf_vote',
        '🐺 Choisissez votre victime',
        'Les loups se concertent. Qui mourra cette nuit ?');
      break;

    case 'seer_reveal':
      _renderVotePanel(panel, action, 'seer_reveal',
        '🔮 Pouvoir de la Voyante',
        'De qui voulez-vous connaître le vrai rôle ?');
      break;

    case 'cupidon_choose':
    case 'cupidon_choose2':
      _renderVotePanel(panel, action, action.type,
        '💘 Cupidon',
        action.extra?.message || 'Choisissez un amoureux');
      break;

    case 'hunter_shoot':
      _renderVotePanel(panel, action, 'hunter_shoot',
        '🏹 Tir du Chasseur',
        'Vous mourez… mais vous emportez quelqu\'un avec vous.');
      break;

    case 'vote':
      _renderVotePanel(panel, action, 'vote',
        '🗳 Vote du village',
        'Qui soupçonnez-vous ? Votez pour l\'éliminer.');
      break;

    case 'witch_action':
      _renderWitchPanel(panel, action);
      break;

    case 'chat':
      _renderChatPanel(panel, action);
      break;

    default:
      panel.innerHTML = `<p style="color:var(--text);font-size:.85rem">En attente…</p>`;
  }
}

function _hideActionPanel() {
  const panel = document.getElementById('action-panel');
  panel.classList.add('hidden');
  panel.innerHTML = '';
}

function _renderVotePanel(panel, action, actionType, title, desc) {
  const h3 = document.createElement('h3');
  h3.textContent = title;
  panel.appendChild(h3);

  const p = document.createElement('p');
  p.textContent = desc;
  panel.appendChild(p);

  const row = document.createElement('div');
  row.className = 'target-buttons';

  (action.targets || []).forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'btn-target';
    btn.textContent = t.name;
    btn.onclick = () => _sendAction(actionType, t.id);
    row.appendChild(btn);
  });

  panel.appendChild(row);
}

function _renderWitchPanel(panel, action) {
  const extra = action.extra || {};
  const victim = extra.victim;
  const healAvail = extra.heal_available;
  const killAvail = extra.kill_available;

  const h3 = document.createElement('h3');
  h3.textContent = '🧙 Tour de la Sorcière';
  panel.appendChild(h3);

  if (victim) {
    const p = document.createElement('p');
    p.innerHTML = `Cette nuit, <strong>${victim}</strong> a été tué·e par les loups.`;
    panel.appendChild(p);
  }

  const row = document.createElement('div');
  row.className = 'btn-witch-row';

  if (healAvail && victim) {
    const btnHeal = document.createElement('button');
    btnHeal.className = 'btn-witch';
    btnHeal.textContent = '💧 Utiliser la potion de vie';
    btnHeal.onclick = () => _sendAction('witch_action', '', { action: 'heal' });
    row.appendChild(btnHeal);
  }

  if (killAvail) {
    const btnKill = document.createElement('button');
    btnKill.className = 'btn-witch danger';
    btnKill.textContent = '☠️ Utiliser la potion de mort…';
    btnKill.onclick = () => _showKillTargets(panel, action.targets);
    row.appendChild(btnKill);
  }

  const btnPass = document.createElement('button');
  btnPass.className = 'btn-witch';
  btnPass.textContent = 'Ne rien faire';
  btnPass.onclick = () => _sendAction('witch_action', '', { action: 'pass' });
  row.appendChild(btnPass);

  panel.appendChild(row);
}

function _showKillTargets(panel, targets) {
  // Remplacer les boutons par la liste de cibles
  const existing = panel.querySelector('.btn-witch-row');
  if (existing) existing.remove();

  const p = document.createElement('p');
  p.textContent = 'Qui empoisonner ?';
  panel.appendChild(p);

  const row = document.createElement('div');
  row.className = 'target-buttons';

  (targets || []).forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'btn-target';
    btn.textContent = t.name;
    btn.onclick = () => _sendAction('witch_action', t.id, { action: 'kill' });
    row.appendChild(btn);
  });

  const btnCancel = document.createElement('button');
  btnCancel.className = 'btn-skip';
  btnCancel.textContent = 'Annuler';
  btnCancel.onclick = () => { row.remove(); p.remove(); btnCancel.remove(); _renderWitchPanel(panel, {}); };

  panel.appendChild(row);
  panel.appendChild(btnCancel);
}

function _renderChatPanel(panel, action) {
  const h3 = document.createElement('h3');
  h3.textContent = '💬 Votre tour de parole';
  panel.appendChild(h3);

  const chatArea = document.createElement('div');
  chatArea.className = 'chat-area';

  const textarea = document.createElement('textarea');
  textarea.placeholder = 'Dites ce que vous pensez, accusez, défendez-vous…';
  textarea.id = 'chat-textarea';

  const actions = document.createElement('div');
  actions.className = 'chat-actions';

  const btnSend = document.createElement('button');
  btnSend.className = 'btn-send';
  btnSend.textContent = 'Envoyer';
  btnSend.onclick = () => {
    const msg = document.getElementById('chat-textarea').value.trim();
    if (!msg) return;
    _sendChat(msg);
  };

  const btnSkip = document.createElement('button');
  btnSkip.className = 'btn-skip';
  btnSkip.textContent = 'Passer';
  btnSkip.onclick = () => _sendChat('');

  // Envoyer avec Entrée (sans Shift)
  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      btnSend.click();
    }
  });

  actions.appendChild(btnSend);
  actions.appendChild(btnSkip);
  chatArea.appendChild(textarea);
  chatArea.appendChild(actions);
  panel.appendChild(chatArea);
  textarea.focus();
}

// -------- Actions réseau --------

async function _sendAction(actionType, targetId, extra) {
  _hideActionPanel();
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_type: actionType, target_id: targetId, extra: extra || {} }),
    });
  } catch (e) {
    _appendLog(`⚠️ Erreur : ${e.message}`, 'system');
  }
}

async function _sendChat(message) {
  _hideActionPanel();
  if (message) {
    _appendLog(`<span class="speaker">Vous</span> : ${message}`, 'npc');
  }
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_type: 'chat', message: message }),
    });
  } catch (e) {
    _appendLog(`⚠️ Erreur : ${e.message}`, 'system');
  }
}

// -------- Fin de partie --------

function _renderGameOver(winner, text) {
  if (sseSource) { sseSource.close(); sseSource = null; }

  const icons = { village: '🌅', loups: '🐺', amoureux: '💕' };
  const titles = {
    village: 'Le Village a gagné !',
    loups: 'Les Loups ont gagné !',
    amoureux: 'Les Amoureux triomphent !',
  };

  document.getElementById('gameover-icon').textContent = icons[winner] || '🏁';
  document.getElementById('gameover-title').textContent = titles[winner] || 'Partie terminée';
  document.getElementById('gameover-text').textContent = text;

  showScreen('gameover-screen');
}

// -------- Modale règles --------

async function loadRules() {
  try {
    const res = await fetch('/api/roles_info');
    const data = await res.json();
    const container = document.getElementById('rules-content');
    container.innerHTML = '';
    for (const [key, role] of Object.entries(data)) {
      const div = document.createElement('div');
      div.className = 'role-entry';
      div.innerHTML = `
        <div class="role-title">${role.emoji} ${role.label}</div>
        <div class="role-team">Équipe : ${role.team === 'loups' ? '🐺 Loups' : '🌾 Village'}</div>
        <div class="role-desc">${role.description}</div>
      `;
      container.appendChild(div);
    }
  } catch (_) {}
}

// -------- Init --------

document.addEventListener('DOMContentLoaded', () => {
  setMode('player');
  loadRules();
});
