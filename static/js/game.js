// ============================================================
// game.js — SSE consumer + UI rendering
// ============================================================

let gameMode = 'player';
let gameStarted = false;
let sseSource = null;
let sseCursor = 0;
let humanPlayerId = null;
let allPlayers = [];  // { id, name, is_human }

// -------- Utilities ---------

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

// -------- Start ----------

async function startGame() {
  const playerName = document.getElementById('input-name').value.trim() || 'Player';
  const roleChoice = document.getElementById('input-role').value;
  const playerCount = parseInt(document.getElementById('input-count').value);

  const btn = document.getElementById('btn-start');
  btn.disabled = true;
  btn.textContent = 'Starting…';

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
    if (!data.ok) throw new Error(data.error || 'Error');

    allPlayers = data.players;
    humanPlayerId = data.mode === 'player' ? 'human' : null;

    const npcPlayers = data.players.filter(p => !p.is_human);
    TTS.assignVoices(npcPlayers);

    if (data.your_role) {
      document.getElementById('header-role').textContent =
        `${data.your_role_emoji} ${data.your_name} — ${data.your_role_label}`;
    } else {
      document.getElementById('header-role').textContent = '👁 Spectator Mode';
    }

    _renderPlayerList(data.players, []);
    showScreen('game-screen');
    _startSSE();

  } catch (e) {
    alert('Start error: ' + e.message);
    btn.disabled = false;
    btn.textContent = 'Start Game';
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
    sseSource.close();
    setTimeout(_startSSE, 2000);
  };
}

// -------- Event handling --------

function _handleEvent(evt) {
  switch (evt.type) {
    case 'narration':
      _appendLog(evt.text, 'narration');
      TTS.speakNarration(evt.text);
      _setTyping(false);
      break;

    case 'npc_dialogue':
      _appendLog(`<span class="speaker">${evt.speaker}</span>: ${evt.text}`, 'npc');
      TTS.speakNPC(evt.text, evt.player_id, evt.speaker);
      break;

    case 'mafia_private':
      if (evt.speaker) {
        _appendLog(`🔫 <span class="speaker">${evt.speaker}</span> (mafia): ${evt.text}`, 'wolf-private');
        TTS.speakWolf(evt.text, evt.player_id || 'mafia');
      } else {
        _appendLog(`🔫 ${evt.text}`, 'wolf-private');
      }
      break;

    case 'role_reveal':
      _appendLog(`⭐ ${evt.text}`, 'secret');
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
    li.textContent = p.is_human ? `${p.name} (you)` : p.name;
    if (p.is_human) li.classList.add('human');
    aliveUl.appendChild(li);
  });
}

function _markDead(playerId, name, roleRevealed) {
  const li = document.getElementById(`player-li-${playerId}`);
  const deadUl = document.getElementById('dead-list');
  const newLi = document.createElement('li');
  newLi.id = `player-li-dead-${playerId}`;
  newLi.innerHTML = name + (roleRevealed ? `<small>${roleRevealed}</small>` : '');
  deadUl.appendChild(newLi);
  if (li) li.remove();
}

function _updatePhaseHeader(phase, round) {
  const phaseLabels = {
    night: '🌙 Night',
    day: '☀️ Day',
    vote: '🗳 Vote',
    game_over: '🏁 End',
  };
  const label = phaseLabels[phase] || phase;
  const r = round || '';
  document.getElementById('header-phase').textContent = `${label} ${r}`.trim();
}

// -------- Action panel --------

function _renderActionPanel(action) {
  const panel = document.getElementById('action-panel');
  panel.classList.remove('hidden');
  panel.innerHTML = '';

  switch (action.type) {
    case 'mafia_vote':
      _renderVotePanel(panel, action, 'mafia_vote',
        '🔫 Choose your target',
        'The mafia deliberates. Who will die tonight?');
      break;

    case 'sheriff_investigate':
      _renderVotePanel(panel, action, 'sheriff_investigate',
        '⭐ Sheriff Investigation',
        'Which player do you want to investigate?');
      break;

    case 'doctor_save':
      _renderDoctorPanel(panel, action);
      break;

    case 'vigilante_shoot':
      _renderVigilantePanel(panel, action);
      break;

    case 'vote':
      _renderVotePanel(panel, action, 'vote',
        '🗳 Town Vote',
        'Who do you suspect? Vote to eliminate them.');
      break;

    case 'chat':
      _renderChatPanel(panel, action);
      break;

    default:
      panel.innerHTML = `<p style="color:var(--text);font-size:.85rem">Waiting…</p>`;
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

function _renderDoctorPanel(panel, action) {
  const h3 = document.createElement('h3');
  h3.textContent = '💉 Doctor — Protect a Player';
  panel.appendChild(h3);

  const p = document.createElement('p');
  p.textContent = 'Choose a player to protect tonight.';
  panel.appendChild(p);

  const row = document.createElement('div');
  row.className = 'target-buttons';

  (action.targets || []).forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'btn-target';
    btn.textContent = t.name;
    btn.onclick = () => _sendAction('doctor_save', t.id);
    row.appendChild(btn);
  });

  panel.appendChild(row);
}

function _renderVigilantePanel(panel, action) {
  const h3 = document.createElement('h3');
  h3.textContent = '🎯 Vigilante — Use Your Shot';
  panel.appendChild(h3);

  const p = document.createElement('p');
  p.textContent = 'You have one shot for the whole game. Choose a target or save it for later.';
  panel.appendChild(p);

  const row = document.createElement('div');
  row.className = 'target-buttons';

  (action.targets || []).forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'btn-target';
    btn.textContent = t.name;
    btn.onclick = () => _sendAction('vigilante_shoot', t.id);
    row.appendChild(btn);
  });

  panel.appendChild(row);

  const btnSkip = document.createElement('button');
  btnSkip.className = 'btn-skip';
  btnSkip.textContent = 'Skip (save shot for later)';
  btnSkip.onclick = () => _sendAction('vigilante_shoot', '');
  panel.appendChild(btnSkip);
}

function _renderChatPanel(panel, action) {
  const h3 = document.createElement('h3');
  h3.textContent = '💬 Your turn to speak';
  panel.appendChild(h3);

  const chatArea = document.createElement('div');
  chatArea.className = 'chat-area';

  const textarea = document.createElement('textarea');
  textarea.placeholder = 'Say what you think, accuse someone, defend yourself…';
  textarea.id = 'chat-textarea';

  const actions = document.createElement('div');
  actions.className = 'chat-actions';

  const btnSend = document.createElement('button');
  btnSend.className = 'btn-send';
  btnSend.textContent = 'Send';
  btnSend.onclick = () => {
    const msg = document.getElementById('chat-textarea').value.trim();
    if (!msg) return;
    _sendChat(msg);
  };

  const btnSkip = document.createElement('button');
  btnSkip.className = 'btn-skip';
  btnSkip.textContent = 'Skip';
  btnSkip.onclick = () => _sendChat('');

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

// -------- Network actions --------

async function _sendAction(actionType, targetId, extra) {
  _hideActionPanel();
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_type: actionType, target_id: targetId, extra: extra || {} }),
    });
  } catch (e) {
    _appendLog(`⚠️ Error: ${e.message}`, 'system');
  }
}

async function _sendChat(message) {
  _hideActionPanel();
  if (message) {
    _appendLog(`<span class="speaker">You</span>: ${message}`, 'npc');
  }
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_type: 'chat', message: message }),
    });
  } catch (e) {
    _appendLog(`⚠️ Error: ${e.message}`, 'system');
  }
}

// -------- Game over --------

function _renderGameOver(winner, text) {
  if (sseSource) { sseSource.close(); sseSource = null; }

  const icons = { town: '🌅', mafia: '🔫', jester: '🃏' };
  const titles = {
    town: 'The Town wins!',
    mafia: 'The Mafia wins!',
    jester: 'The Jester wins!',
  };

  document.getElementById('gameover-icon').textContent = icons[winner] || '🏁';
  document.getElementById('gameover-title').textContent = titles[winner] || 'Game over';
  document.getElementById('gameover-text').textContent = text;

  showScreen('gameover-screen');
}

// -------- Rules modal --------

async function loadRules() {
  try {
    const res = await fetch('/api/roles_info');
    const data = await res.json();
    const container = document.getElementById('rules-content');
    container.innerHTML = '';
    for (const [key, role] of Object.entries(data)) {
      const div = document.createElement('div');
      div.className = 'role-entry';
      const teamLabel = role.team === 'mafia' ? '🔫 Mafia'
                      : role.team === 'jester' ? '🃏 Neutral'
                      : '🏘️ Town';
      div.innerHTML = `
        <div class="role-title">${role.emoji} ${role.label}</div>
        <div class="role-team">Team: ${teamLabel}</div>
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
