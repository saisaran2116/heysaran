/**
 * Hey Saran - Siri Assistant Frontend Controller
 * Communicates with the Python backend via WebSocket IPC (ws://127.0.0.1:8765/ws)
 * Automatically reacts to wake-word activations without requiring manual clicks!
 */

(function () {
  'use strict';

  // DOM Elements
  const statusPill = document.getElementById('statusPill');
  const statusLabel = document.getElementById('statusLabel');
  const orbWrapper = document.getElementById('orbWrapper');
  const siriOrb = document.getElementById('siriOrb');
  const voiceStatusText = document.getElementById('voiceStatusText');
  const chatViewport = document.getElementById('chatViewport');
  const emptyState = document.getElementById('emptyState');
  const messagesList = document.getElementById('messagesList');
  const inputForm = document.getElementById('inputForm');
  const userInput = document.getElementById('userInput');
  const micBtn = document.getElementById('micBtn');
  const clearBtn = document.getElementById('clearBtn');
  const settingsToggleBtn = document.getElementById('settingsToggleBtn');
  const settingsDrawer = document.getElementById('settingsDrawer');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const minimizeBtn = document.getElementById('minimizeBtn');
  const testVoiceBtn = document.getElementById('testVoiceBtn');
  const testNotificationBtn = document.getElementById('testNotificationBtn');

  // State tracking
  let ws = null;
  let currentState = 'idle';
  let reconnectTimer = null;

  // ---------------------------------------------------------------------------
  // 1. WebSocket IPC Connection
  // ---------------------------------------------------------------------------
  function connectWebSocket() {
    const wsUrl = `ws://${window.location.hostname || '127.0.0.1'}:8766`;
    console.log('[Hey Saran] Connecting to backend WebSocket:', wsUrl);

    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      console.error('[Hey Saran] WebSocket creation failed:', e);
      scheduleReconnect();
      return;
    }

    ws.onopen = function () {
      console.log('[Hey Saran] Connected to Python assistant backend.');
      setOrbState('idle');
      // Request initial status info
      sendMessage({ type: 'get_status' });
    };

    ws.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
      } catch (err) {
        console.error('[Hey Saran] Error parsing server message:', err);
      }
    };

    ws.onclose = function () {
      console.warn('[Hey Saran] WebSocket disconnected. Retrying in 2 seconds...');
      setOrbState('offline');
      scheduleReconnect();
    };

    ws.onerror = function (err) {
      console.error('[Hey Saran] WebSocket error:', err);
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectWebSocket, 2000);
  }

  function sendMessage(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    } else {
      console.warn('[Hey Saran] WebSocket not connected. Message queued or dropped:', payload);
    }
  }

  // ---------------------------------------------------------------------------
  // 2. Event Dispatcher & State Handling
  // ---------------------------------------------------------------------------
  function handleServerEvent(data) {
    const { event, text, status, mode } = data;

    switch (event) {
      case 'wake_word_triggered':
        // Core Requirement: Wake-word instantly activates listening mode!
        console.log('[Hey Saran] >>> Wake Word Detected by Backend <<<');
        setOrbState('listening');
        voiceStatusText.innerHTML = `Listening... <strong class="keyword">speak your command</strong>`;
        break;

      case 'transcript':
        // User finished speaking, add user message bubble
        if (text && text.trim()) {
          appendMessage('user', text.trim());
          setOrbState('thinking');
        }
        break;

      case 'assistant_message':
        // Assistant responded, add assistant message bubble
        if (text && text.trim()) {
          appendMessage('assistant', text.trim());
          setOrbState('speaking');
        }
        break;

      case 'state':
        // Backend informs UI of state change (idle, listening, thinking, speaking, error)
        if (status) {
          setOrbState(status);
        }
        break;

      case 'status_info':
        updateSettingsInfo(data);
        break;

      case 'error':
        setOrbState('error');
        if (text) {
          voiceStatusText.textContent = text;
        }
        setTimeout(() => setOrbState('idle'), 3500);
        break;

      default:
        console.log('[Hey Saran] Unhandled event:', data);
    }
  }

  function setOrbState(state) {
    currentState = state;
    orbWrapper.setAttribute('data-state', state);
    statusPill.setAttribute('data-status', state);

    // Format human-readable status label
    const labels = {
      idle: 'Idle',
      listening: 'Listening...',
      thinking: 'Thinking...',
      speaking: 'Speaking...',
      error: 'Error',
      offline: 'Offline'
    };
    statusLabel.textContent = labels[state] || state;

    // Subtitle prompt text updates
    if (state === 'idle') {
      voiceStatusText.innerHTML = `Say <strong class="keyword">"Hey Saran"</strong> to talk`;
      micBtn.classList.remove('active');
    } else if (state === 'listening') {
      voiceStatusText.innerHTML = `Listening... <strong class="keyword">speak now</strong>`;
      micBtn.classList.add('active');
    } else if (state === 'thinking') {
      voiceStatusText.innerHTML = `Processing with <strong class="keyword">Sarvam AI</strong>...`;
      micBtn.classList.remove('active');
    } else if (state === 'speaking') {
      voiceStatusText.innerHTML = `Hey Saran is speaking...`;
      micBtn.classList.remove('active');
    } else if (state === 'offline') {
      voiceStatusText.textContent = `Connecting to assistant engine...`;
      micBtn.classList.remove('active');
    }
  }

  // ---------------------------------------------------------------------------
  // 3. Message Rendering
  // ---------------------------------------------------------------------------
  function appendMessage(sender, text) {
    if (emptyState.style.display !== 'none') {
      emptyState.style.display = 'none';
    }

    const row = document.createElement('div');
    row.className = `message-row ${sender === 'user' ? 'user-row' : 'assistant-row'}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = text;

    const meta = document.createElement('div');
    meta.className = 'message-meta';

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const timeSpan = document.createElement('span');
    timeSpan.textContent = timeStr;
    meta.appendChild(timeSpan);

    if (sender === 'assistant') {
      const copyBtn = document.createElement('button');
      copyBtn.className = 'copy-btn';
      copyBtn.textContent = 'Copy';
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(text);
        copyBtn.textContent = 'Copied!';
        setTimeout(() => (copyBtn.textContent = 'Copy'), 1500);
      };
      meta.appendChild(copyBtn);
    }

    row.appendChild(bubble);
    row.appendChild(meta);
    messagesList.appendChild(row);

    // Auto-scroll to bottom
    chatViewport.scrollTop = chatViewport.scrollHeight;
  }

  // ---------------------------------------------------------------------------
  // 4. UI Actions & Controls
  // ---------------------------------------------------------------------------

  // Text input submit
  inputForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    userInput.value = '';
    setOrbState('thinking');

    sendMessage({
      type: 'user_text',
      text: text
    });
  });

  // Manual Microphone toggle button
  micBtn.addEventListener('click', function () {
    if (currentState === 'listening') {
      setOrbState('idle');
      sendMessage({ type: 'stop_listening' });
    } else {
      setOrbState('listening');
      sendMessage({ type: 'start_listening' });
    }
  });

  // Clicking the glowing orb triggers listening directly
  siriOrb.addEventListener('click', function () {
    if (currentState === 'idle') {
      setOrbState('listening');
      sendMessage({ type: 'start_listening' });
    }
  });

  // Suggestion chips
  document.querySelectorAll('.suggestion-chip').forEach((chip) => {
    chip.addEventListener('click', function () {
      const query = this.getAttribute('data-query');
      if (query) {
        appendMessage('user', query);
        setOrbState('thinking');
        sendMessage({
          type: 'user_text',
          text: query
        });
      }
    });
  });

  // Clear conversation button
  clearBtn.addEventListener('click', function () {
    messagesList.innerHTML = '';
    emptyState.style.display = 'flex';
    setOrbState('idle');
    sendMessage({ type: 'clear_conversation' });
  });

  // Settings drawer toggle
  settingsToggleBtn.addEventListener('click', function () {
    settingsDrawer.classList.add('open');
    settingsDrawer.setAttribute('aria-hidden', 'false');
  });

  closeSettingsBtn.addEventListener('click', function () {
    settingsDrawer.classList.remove('open');
    settingsDrawer.setAttribute('aria-hidden', 'true');
  });

  // Minimize window via backend
  minimizeBtn.addEventListener('click', function () {
    sendMessage({ type: 'minimize_window' });
  });

  // Settings: Mode switch
  document.querySelectorAll('.segment-btn').forEach((btn) => {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.segment-btn').forEach((b) => b.classList.remove('active'));
      this.classList.add('active');
      const selectedMode = this.getAttribute('data-mode');
      const modeHint = document.getElementById('modeHint');
      if (selectedMode === 'phrase') {
        modeHint.textContent = 'Active: Listens continuously for "Hey Saran" voice commands.';
      } else {
        modeHint.textContent = 'Active: openWakeWord ONNX neural model (models/hey_saran.onnx or alexa).';
      }
      sendMessage({ type: 'set_mode', mode: selectedMode });
    });
  });

  // Settings: Test buttons
  testVoiceBtn.addEventListener('click', function () {
    sendMessage({ type: 'test_voice' });
  });

  testNotificationBtn.addEventListener('click', function () {
    sendMessage({ type: 'test_notification' });
  });

  function updateSettingsInfo(info) {
    if (info.sarvam_available !== undefined) {
      const badge = document.getElementById('sarvamStatusBadge');
      if (badge) {
        badge.className = `status-badge ${info.sarvam_available ? 'connected' : 'fallback'}`;
        badge.textContent = info.sarvam_available ? 'Connected' : 'Offline';
      }
    }
  }

  // Keyboard shortcut: Escape closes settings or minimizes
  window.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (settingsDrawer.classList.contains('open')) {
        settingsDrawer.classList.remove('open');
      } else {
        sendMessage({ type: 'minimize_window' });
      }
    }
  });

  // Initialize connection
  connectWebSocket();
})();
