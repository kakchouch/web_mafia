// TTS — Web Speech API, voix françaises, voix distinctes par joueur

const TTS = (() => {
  let muted = false;
  const queue = [];
  let speaking = false;

  // playerId -> { voice, pitch, rate }
  const playerVoices = {};
  let frVoices = [];
  let voicesReady = false;

  function loadVoices() {
    const all = speechSynthesis.getVoices();
    frVoices = all.filter(v => v.lang.startsWith('fr'));
    if (frVoices.length === 0) frVoices = all; // fallback
    voicesReady = frVoices.length > 0;

    const statusEl = document.getElementById('voice-status');
    if (statusEl) {
      statusEl.textContent = voicesReady
        ? `${frVoices.length} voix FR`
        : 'Voix par défaut';
    }
  }

  // Appel au démarrage du jeu avec la liste des joueurs PNJ
  function assignVoices(players) {
    loadVoices();

    // Narrateur : voix 0, pitch grave
    playerVoices['narrator'] = {
      voice: frVoices[0] || null,
      pitch: 0.65,
      rate: 0.82,
    };

    // Chaque joueur reçoit une combinaison unique
    players.forEach((p, i) => {
      const voiceIndex = i % Math.max(frVoices.length, 1);
      const pitch = 0.75 + ((i * 17) % 55) / 100;   // 0.75 – 1.30
      const rate  = 0.88 + ((i * 11) % 22) / 100;   // 0.88 – 1.10

      playerVoices[p.id] = {
        voice: frVoices[voiceIndex] || frVoices[0] || null,
        pitch,
        rate,
      };
    });
  }

  function _speak(text, voiceConfig, priority = false) {
    if (muted) return;
    const item = { text, voiceConfig, priority };
    if (priority) {
      speechSynthesis.cancel();
      queue.length = 0;
      queue.unshift(item);
    } else {
      queue.push(item);
    }
    if (!speaking) _next();
  }

  function _next() {
    if (queue.length === 0) { speaking = false; return; }
    speaking = true;
    const { text, voiceConfig } = queue.shift();

    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = 'fr-FR';
    if (voiceConfig) {
      if (voiceConfig.voice) utt.voice = voiceConfig.voice;
      if (voiceConfig.pitch !== undefined) utt.pitch = voiceConfig.pitch;
      if (voiceConfig.rate  !== undefined) utt.rate  = voiceConfig.rate;
    }

    utt.onend = () => _next();
    utt.onerror = () => _next();

    speechSynthesis.speak(utt);
  }

  function speakNarration(text) {
    _speak(text, playerVoices['narrator'] || null, true);
  }

  function speakNPC(text, playerId, speakerName) {
    const cfg = playerVoices[playerId] || null;
    _speak(text, cfg, false);
  }

  function speakSecret(text) {
    // Message privé, chuchoté (pitch haut, rate lent)
    _speak(text, { voice: frVoices[0] || null, pitch: 1.4, rate: 0.75 }, false);
  }

  function toggleMute() {
    muted = !muted;
    const btn = document.getElementById('btn-mute');
    if (muted) {
      speechSynthesis.cancel();
      queue.length = 0;
      speaking = false;
      if (btn) btn.textContent = '🔇';
    } else {
      if (btn) btn.textContent = '🔊';
    }
  }

  // Certains navigateurs chargent les voix de façon asynchrone
  if (typeof speechSynthesis !== 'undefined') {
    if (speechSynthesis.onvoiceschanged !== undefined) {
      speechSynthesis.onvoiceschanged = loadVoices;
    }
    loadVoices();
  }

  return { assignVoices, speakNarration, speakNPC, speakSecret, toggleMute };
})();
