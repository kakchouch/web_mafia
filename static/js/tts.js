// TTS — Kokoro backend via /api/tts
// Règles :
//  - Une seule voix à la fois (file FIFO stricte)
//  - Narration prioritaire : coupe l'audio en cours immédiatement
//  - Après chaque dialogue PNJ : envoie un ACK au backend pour le synchroniser
//  - Pause de 500 ms entre chaque prise de parole

const TTS = (() => {
  let muted = false;
  const queue = [];
  let playing = false;

  // Compteur de génération : invalide les callbacks d'audio périmés
  let generation = 0;

  // Référence à l'Audio en cours pour pouvoir le couper
  let currentAudio = null;

  // Multiplicateur de vitesse global (0.5 – 2.5)
  let speedMultiplier = 1.0;

  // playerId -> { character_index } ou { is_narrator: true }
  const playerConfig = {};

  // ---------------------------------------------------------------------------
  // Init (appelé après /api/game/start)
  // ---------------------------------------------------------------------------
  function assignVoices(players) {
    players.forEach(p => {
      if (p.is_human) {
        playerConfig[p.id] = { character_index: null };
      } else {
        playerConfig[p.id] = { character_index: p.voice_index, gender: p.gender || 'm' };
      }
    });
    playerConfig['narrator'] = { is_narrator: true };

    const statusEl = document.getElementById('voice-status');
    if (statusEl) statusEl.textContent = 'Kokoro TTS';
  }

  // ---------------------------------------------------------------------------
  // File d'attente
  // ---------------------------------------------------------------------------
  function _enqueue(text, config, priority = false) {
    if (muted || !text || !text.trim()) return;

    const item = { text: text.trim(), config };

    if (priority) {
      // Couper immédiatement l'audio en cours
      generation++;
      if (currentAudio) {
        currentAudio.onended = null;
        currentAudio.onerror = null;
        try { currentAudio.pause(); } catch (_) {}
        currentAudio = null;
      }
      // Vider la file, mettre la narration en tête
      queue.length = 0;
      queue.unshift(item);
      playing = false;  // forcer la relance
    } else {
      queue.push(item);
    }

    if (!playing) _next();
  }

  async function _next() {
    if (queue.length === 0) { playing = false; return; }
    playing = true;

    const { text, config } = queue.shift();
    const myGen = ++generation;

    try {
      const body = { text, speed_multiplier: speedMultiplier };
      if (config.is_narrator) {
        body.is_narrator = true;
      } else if (config.character_index != null) {
        body.character_index = config.character_index;
        body.gender = config.gender || 'm';
      }

      const resp = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      // Callback périmé ? (une narration prioritaire est arrivée entre-temps)
      if (generation !== myGen) return;
      if (!resp.ok) { _nextWithPause(myGen); return; }

      const blob = await resp.blob();
      if (generation !== myGen) return;

      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudio = audio;

      audio.onended = () => {
        URL.revokeObjectURL(url);
        currentAudio = null;
        if (generation !== myGen) return;  // périmé
        // ACK backend si ce dialogue en avait besoin
        if (config.needs_ack) {
          fetch('/api/tts/ack', { method: 'POST' }).catch(() => {});
        }
        _nextWithPause(myGen);
      };

      audio.onerror = () => {
        URL.revokeObjectURL(url);
        currentAudio = null;
        if (generation !== myGen) return;
        if (config.needs_ack) {
          fetch('/api/tts/ack', { method: 'POST' }).catch(() => {});
        }
        _nextWithPause(myGen);
      };

      await audio.play();

    } catch (_) {
      currentAudio = null;
      if (generation !== myGen) return;
      if (config.needs_ack) {
        fetch('/api/tts/ack', { method: 'POST' }).catch(() => {});
      }
      _nextWithPause(myGen);
    }
  }

  // Pause de 500 ms entre les prises de parole
  function _nextWithPause(myGen) {
    setTimeout(() => {
      if (generation !== myGen) return;
      _next();
    }, 500);
  }

  // ---------------------------------------------------------------------------
  // API publique
  // ---------------------------------------------------------------------------
  function speakNarration(text) {
    // Prioritaire — interrompt tout
    _enqueue(text, { is_narrator: true }, true);
  }

  function speakNPC(text, playerId) {
    const cfg = { ...(playerConfig[playerId] || { character_index: 0 }), needs_ack: true };
    _enqueue(text, cfg, false);
  }

  function speakWolf(text, playerId) {
    // Dialogues loups : ACK aussi (backend attend)
    const cfg = { ...(playerConfig[playerId] || { character_index: 0 }), needs_ack: true };
    _enqueue(text, cfg, false);
  }

  function speakSecret(text) {
    _enqueue(text, { is_narrator: true }, false);
  }

  function setSpeed(multiplier) {
    speedMultiplier = Math.max(0.5, Math.min(2.5, parseFloat(multiplier) || 1.0));
  }

  function toggleMute() {
    muted = !muted;
    const btn = document.getElementById('btn-mute');
    if (muted) {
      generation++;
      queue.length = 0;
      playing = false;
      if (currentAudio) {
        try { currentAudio.pause(); } catch (_) {}
        currentAudio = null;
      }
      if (btn) btn.textContent = '🔇';
    } else {
      if (btn) btn.textContent = '🔊';
    }
  }

  return { assignVoices, speakNarration, speakNPC, speakWolf, speakSecret, toggleMute, setSpeed };
})();
