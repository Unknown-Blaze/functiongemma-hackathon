const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const runTextBtn = document.getElementById('runTextBtn');
const transcriptEl = document.getElementById('transcript');
const statusEl = document.getElementById('status');
const sourceChip = document.getElementById('sourceChip');
const confidenceChip = document.getElementById('confidenceChip');
const timeChip = document.getElementById('timeChip');
const assistantResponseEl = document.getElementById('assistantResponse');
const callsEl = document.getElementById('calls');
const actionsEl = document.getElementById('actions');

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

function setStatus(text) {
  statusEl.textContent = text;
}

async function parseJsonSafe(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { error: text };
  }
}

async function postJson(url, payload) {
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch (err) {
    throw new Error('Cannot reach backend API. Make sure you opened http://127.0.0.1:8080 and server is running.');
  }

  const data = await parseJsonSafe(response);
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

function renderActions(actions) {
  actionsEl.innerHTML = '';
  if (!actions || actions.length === 0) {
    const li = document.createElement('li');
    li.textContent = 'No actions returned.';
    actionsEl.appendChild(li);
    return;
  }
  actions.forEach(action => {
    const li = document.createElement('li');
    li.textContent = action;
    actionsEl.appendChild(li);
  });
}

function renderResult(data) {
  sourceChip.textContent = `source: ${data.source || '-'}`;
  confidenceChip.textContent = `confidence: ${Number(data.confidence || 0).toFixed(3)}`;
  timeChip.textContent = `time: ${Math.round(data.total_time_ms || 0)}ms`;
  assistantResponseEl.textContent = data.assistant_response || 'No response generated.';
  callsEl.textContent = JSON.stringify(data.function_calls || [], null, 2);
  renderActions(data.actions || []);
}

async function runWorkflow() {
  const transcript = transcriptEl.value.trim();
  if (!transcript) {
    setStatus('Please provide a transcript first.');
    return;
  }

  setStatus('Routing transcript...');
  runTextBtn.disabled = true;

  try {
    const data = await postJson('/api/route', { transcript });
    renderResult(data);
    setStatus(data.assistant_response || 'Done.');
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  } finally {
    runTextBtn.disabled = false;
  }
}

function initSpeech() {
  if (!SpeechRecognition) {
    setStatus('Speech recognition not available in this browser. Use text input + Run Text.');
    startBtn.disabled = true;
    stopBtn.disabled = true;
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.continuous = false;
  recognition.interimResults = true;

  recognition.onstart = () => {
    setStatus('Listening...');
    startBtn.disabled = true;
    stopBtn.disabled = false;
  };

  recognition.onresult = (event) => {
    let finalText = '';
    let interimText = '';

    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const text = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalText += text;
      } else {
        interimText += text;
      }
    }

    const merged = (finalText || interimText).trim();
    if (merged) transcriptEl.value = merged;
  };

  recognition.onerror = (event) => {
    setStatus(`Speech error: ${event.error}`);
  };

  recognition.onend = () => {
    startBtn.disabled = false;
    stopBtn.disabled = true;
    setStatus('Stopped listening. Click Run Text to route.');
  };
}

async function runStartupChecks() {
  if (window.location.protocol === 'file:') {
    setStatus('You are on file://. Run python voice_web_server.py and open http://127.0.0.1:8080');
    return;
  }

  try {
    const response = await fetch('/api/health');
    const data = await parseJsonSafe(response);
    if (!response.ok || !data.ok) {
      setStatus('Backend health check failed. Is voice_web_server.py running?');
      return;
    }

    if (!data.cactus_bindings) {
      setStatus('Backend up, but cactus Python bindings not available. Re-run cactus setup and env.');
      return;
    }

    if (!data.whisper_weights_exists || !data.whisper_config_exists) {
      setStatus(`Backend up. Whisper missing at ${data.whisper_weights_path}. Download whisper-small weights.`);
      return;
    }

    setStatus('Ready. Mic + backend checks look good.');
  } catch {
    setStatus('Cannot reach backend. Start server with: python voice_web_server.py');
  }
}

startBtn.addEventListener('click', () => {
  if (!recognition) return;
  transcriptEl.value = '';
  recognition.start();
});

stopBtn.addEventListener('click', () => {
  if (!recognition) return;
  recognition.stop();
});

runTextBtn.addEventListener('click', runWorkflow);

initSpeech();
runStartupChecks();
