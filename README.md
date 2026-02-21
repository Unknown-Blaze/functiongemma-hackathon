<img src="assets/banner.png" alt="Logo" style="border-radius: 30px; width: 100%;">

Team Name: Native Hackers
Explanation Doc: https://docs.google.com/document/d/1fffZejJ8XaPDakSoqIOXBrz-u-CdRXswwgYl7AwfYwA/edit?usp=sharing

## Quick Run Guide

From this repository root:

1. Run local eval:

```bash
python benchmark.py
```

2. Submit to leaderboard:

```bash
python submit.py --team "YourTeam" --location "Singapore"
```

3. Run voice-to-action SPA:

```bash
python voice_web_server.py
```

Then open:

```text
http://127.0.0.1:8080
```

For backend transcription in the SPA, ensure Whisper weights exist:

```bash
cactus download openai/whisper-small --reconvert
```

## Context
- Cactus runs Google DeepMind's FunctionGemma at up to 3000 toks/sec prefill speed on M4 Macs.
- While decode speed reaches 200 tokens/sec, all without GPU, to remain energy-efficient. 
- FunctionGemma is great at tool calling, but small models are not the smartest for some tasks. 
- There is a need to dynamically combine edge and cloud (Gemini Flash) to get the best of both worlds. 
- Cactus develops various strategies for choosing when to fall back to Gemini or FunctionGemma.

## Challenge
- FunctionGemma is just a tool-call model, but tool calling is the core of agentic systems. 
- You MUST design new strategies that decide when to stick with on-device or fall to cloud. 
- You will be objectively ranked on tool-call correctness, speed and edge/cloud ratio (priortize local). 
- You can focus on prompting, tool description patterns, confidence score algorithms, anything!
- Please ensure at least 1 team member has a Mac, Cactus runs on Macs, mobile devices and wearables.

## Setup (clone this repo and hollistically follow)
- Step 1: Fork this repo, clone to your Mac, open terminal.
- Step 2: `git clone https://github.com/cactus-compute/cactus`
- Step 3: `cd cactus && source ./setup && cd ..` (re-run in new terminal)
- Step 4: `cactus build --python`
- Step 5: `cactus download google/functiongemma-270m-it --reconvert`
- Step 6: Get cactus key from the [cactus website](https://cactuscompute.com/dashboard/api-keys)
- Sept 7: Run `cactus auth` and enter your token when prompted.
- Step 8: `pip install google-genai`
- Step 9: Obtain Gemini API key from [Google AI Studio](https://aistudio.google.com/api-keys)
- Step 10: `export GEMINI_API_KEY="your-key"`
- Step 11: Click on location to get Gemini credits - [SF](https://trygcp.dev/claim/cactus-x-gdm-hackathon-sf), [Boston](https://trygcp.dev/claim/cactus-x-gdm-hackathon-boston), [DC](https://trygcp.dev/claim/cactus-x-gdm-hackathon-dc), [London](https://trygcp.dev/claim/cactus-x-gdm-hackathon-london), [Singapore](https://trygcp.dev/claim/cactus-x-gdm-hackathon), [Online](https://trygcp.dev/claim/cactus-x-gdm-hackathon-online)
- Step 12: Join the [Reddit channel](https://www.reddit.com/r/cactuscompute/), ask any technical questions there.
- Step 13: read and run `python benchmark.py` to understand how objective scoring works.
- Note: Final objective score will be done on held-out evals, top 10 are then judged subjectively.

## Submissions
- Your main task is to modify the **internal logic** of the `generate_hybrid` method in `main.py`. 
- Do not modify the input or output signature (function arguments and return variables) of the `generate_hybrid` method. Keep the hybrid interface compatible with `benchmark.py`.
- Submit to the leaderboard `python submit.py --team "YourTeamName" --location "YourCity"`, only 1x every 1hr.
- The dataset is a hidden Cactus eval, quite difficult for FunctionGemma by design.
- Use `python benchmark.py` to iterate, but your best score is preserved.
- For transparency, hackers can see live rankings on the [leaderboard](https://cactusevals.ngrok.app).
- Leaderboard will start accepting submissions once event starts. 
- The top 10 in each location will make it to judging.

## Qualitative Judging 
- **Rubric 1**: The quality of your hybrid routing algorithm, depth and cleverness.
- **Rubric 2**: End-to-end products that execute function calls to solve real-world problems. 
- **Rubric 3**: Building low-latency voice-to-action products, leveraging `cactus_transcribe`.

## Quick Example

```python
import json
from cactus import cactus_init, cactus_complete, cactus_destroy

model = cactus_init("weights/lfm2-vl-450m")
messages = [{"role": "user", "content": "What is 2+2?"}]
response = json.loads(cactus_complete(model, messages))
print(response["response"])

cactus_destroy(model)

## API Reference
|-----------|------|-------------|
| `model_path` | `str` | Path to model weights directory |
model = cactus_init("weights/lfm2-vl-450m")
model = cactus_init("weights/lfm2-rag", corpus_dir="./documents")
```

### `cactus_complete(model, messages, **options)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | handle | Model handle from `cactus_init` |
| `messages` | `list\|str` | List of message dicts or JSON string |
| `tools` | `list` | Optional tool definitions for function calling |
| `temperature` | `float` | Sampling temperature |
| `top_p` | `float` | Top-p sampling |
| `top_k` | `int` | Top-k sampling |
| `max_tokens` | `int` | Maximum tokens to generate |
| `stop_sequences` | `list` | Stop sequences |
| `include_stop_sequences` | `bool` | Include matched stop sequences in output (default: `False`) |
| `force_tools` | `bool` | Constrain output to tool call format |
| `tool_rag_top_k` | `int` | Select top-k relevant tools via Tool RAG (default: 2, 0 = use all tools) |
| `confidence_threshold` | `float` | Minimum confidence for local generation (default: 0.7, triggers cloud_handoff when below) |
| `callback` | `fn` | Streaming callback `fn(token, token_id, user_data)` |

```python
# Basic completion
messages = [{"role": "user", "content": "Hello!"}]
response = cactus_complete(model, messages, max_tokens=100)
print(json.loads(response)["response"])
```

```python
# Completion with tools
tools = [{
    "name": "get_weather",
    "description": "Get weather for a location",
    "parameters": {
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"]
    }
}]

response = cactus_complete(model, messages, tools=tools)
cactus_complete(model, messages, callback=on_token)
```

**Response format** (all fields always present):
```json
{
    "success": true,
    "error": null,
    "cloud_handoff": false,
    "response": "Hello! How can I help?",
    "function_calls": [],
    "confidence": 0.85,
    "time_to_first_token_ms": 45.2,
    "total_time_ms": 163.7,
    "prefill_tps": 619.5,
    "decode_tps": 168.4,
    "ram_usage_mb": 245.67,
    "prefill_tokens": 28,
    "decode_tokens": 50,
    "total_tokens": 78
}
```

**Cloud handoff response** (when model detects low confidence):
```json
{
    "success": false,
    "error": null,
    "cloud_handoff": true,
    "response": null,
    "function_calls": [],
    "confidence": 0.18,
    "time_to_first_token_ms": 45.2,
    "total_time_ms": 45.2,
    "prefill_tps": 619.5,
    "decode_tps": 0.0,
    "ram_usage_mb": 245.67,
    "prefill_tokens": 28,
    "decode_tokens": 0,
    "total_tokens": 28
}
```

- When `cloud_handoff` is `True`, the model's confidence dropped below `confidence_threshold` (default: 0.7) and recommends deferring to a cloud-based model for better results. 

- You will NOT rely on this, hackers must design custom strategies to fall-back to cloud, that maximizes on-devices and correctness, while minimizing end-to-end latency!

### `cactus_transcribe(model, audio_path, prompt="")`

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | handle | Whisper model handle |
| `audio_path` | `str` | Path to audio file (WAV) |
| `prompt` | `str` | Whisper prompt for language/task |

```python
whisper = cactus_init("weights/whisper-small")
prompt = "<|startoftranscript|><|en|><|transcribe|><|notimestamps|>"
response = cactus_transcribe(whisper, "audio.wav", prompt=prompt)
print(json.loads(response)["response"])
cactus_destroy(whisper)
```

### `cactus_embed(model, text, normalize=False)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | handle | Model handle |
| `text` | `str` | Text to embed |
| `normalize` | `bool` | L2-normalize embeddings (default: False) |

```python
embedding = cactus_embed(model, "Hello world")
print(f"Dimension: {len(embedding)}")
```

### `cactus_reset(model)`

Reset model state (clear KV cache). Call between unrelated conversations.

```python
cactus_reset(model)
```

### `cactus_stop(model)`

Stop an ongoing generation (useful with streaming callbacks).

```python
cactus_stop(model)
```

### `cactus_destroy(model)`

Free model memory. Always call when done.

```python
cactus_destroy(model)
```

### `cactus_get_last_error()`

Get the last error message, or `None` if no error.

```python
error = cactus_get_last_error()
if error:
    print(f"Error: {error}")
```

### `cactus_rag_query(model, query, top_k=5)`

Query RAG corpus for relevant text chunks. Requires model initialized with `corpus_dir`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | handle | Model handle (must have corpus_dir set) |
| `query` | `str` | Query text |
| `top_k` | `int` | Number of chunks to retrieve (default: 5) |

```python
model = cactus_init("weights/lfm2-rag", corpus_dir="./documents")
chunks = cactus_rag_query(model, "What is machine learning?", top_k=3)
for chunk in chunks:
    print(f"Score: {chunk['score']:.2f} - {chunk['text'][:100]}...")
```

## Next steps:
- Join the [Reddit channel](https://www.reddit.com/r/cactuscompute/), ask any technical questions there.
- To gain some technical insights on AI, checkout [Maths, CS & AI Compendium](https://github.com/HenryNdubuaku/maths-cs-ai-compendium). 

## Simple Voice-to-Action Web Demo

Run a minimal browser workflow that captures voice, routes transcript through `generate_hybrid`, and shows function calls/actions.

1. Start server:

```bash
python voice_web_server.py
```

2. Open in browser:

```text
http://127.0.0.1:8080
```

3. Click **Start Listening**, speak, then **Run Text**.

Notes:
- Speech recognition uses the browser Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`).
- If speech recognition is unavailable, type into the transcript box and click **Run Text**.
- Backend voice transcription endpoint is `/api/transcribe_route` and uses `cactus_transcribe` with `weights/whisper-small`.
- Ensure Whisper weights are downloaded first (e.g. `cactus download openai/whisper-small --reconvert`).

## Submission Checklist (Recommended)

Before final submission, quickly verify:

1. `python benchmark.py` runs end-to-end with no crashes.
2. `generate_hybrid` signature in `main.py` is unchanged.
3. `python submit.py --team "YourTeam" --location "Singapore"` works from repo root.
4. No local-only hacks are required for runtime (paths/env assumptions are robust).
5. README reflects current behavior (especially UI controls and routing behavior).

## 6-7 Minute Presentation Script

Use this script for a longer final presentation.

### 0:00 - 0:40 | Opening and problem framing
"We built a hybrid voice-to-action assistant for the FunctionGemma x Cactus hackathon. The core problem is balancing three things at once: tool-call correctness, latency, and on-device ratio. Small models are fast and private on device, but difficult prompts can still need fallback strategies. So our work focused on a router that is robust, interpretable, and practical in a real demo UX."

### 0:40 - 1:40 | Architecture overview
"At a high level, there are two layers. First is the routing layer in `main.py`, centered on `generate_hybrid`. Second is a thin full-stack demo layer using `voice_web_server.py` and a SPA in `web/` so judges can see voice and text become executable actions in real time."

"The key architectural decision is on-device-first routing with controlled fallback. We intentionally avoid blindly using cloud because leaderboard scoring values on-device behavior and latency."

### 1:40 - 3:10 | Main technique: hybrid router in `main.py`
"`generate_hybrid` follows a staged strategy. Stage one runs local FunctionGemma through Cactus and validates tool calls. Stage two applies a deterministic schema router as fallback when the model output is weak, empty, or underspecified. Stage three keeps cloud fallback available for truly low-confidence situations."

"Two implementation details matter a lot here. First, schema-aware validation and normalization: required fields, type checks, integer coercion, and time canonicalization. That prevents malformed calls from being accepted. Second, merge + dedupe logic: we combine model and parser strengths so compound prompts are handled better and repeated calls are filtered."

### 3:10 - 4:20 | Robustness and generalization choices
"A major challenge in hidden evals is phrasing drift. We improved resilience with broader extraction patterns for timer/alarm/message/reminder/weather, plus fallback behavior that still returns best local attempts when confidence is decent. This reduces all-or-nothing failures."

"We also hardened path/environment behavior, because submission environments may differ from local assumptions. That includes model path resolution and safer runtime handling so the app degrades gracefully instead of crashing."

### 4:20 - 5:20 | UI demo walkthrough
"In the web app, we click Start Listening, speak a command, and Run Text. The interface shows transcript, route metadata, function calls, workflow actions, and a clean assistant response."

"For weather queries, we don’t stop at tool selection. The backend executes a real weather fetch via Open-Meteo and returns an actual natural-language weather answer. That makes the demo feel like a usable product rather than a raw tool-call inspector."

### 5:20 - 6:20 | Why this is strong for judging
"This approach scores well across both objective and qualitative axes. Objectively, it targets correctness with low latency and strong on-device usage. Qualitatively, it demonstrates system design: routing logic, confidence handling, fallback strategy, and an end-to-end interaction layer."

"It is also explainable. Each stage has a clear purpose, clear acceptance criteria, and clear failure behavior. That makes it easy to defend technical choices under judging questions."

### 6:20 - 7:00 | Closing
"In summary, we built an edge-first hybrid assistant that is practical and demo-ready: robust routing in `main.py`, controlled fallback, schema-safe tool execution, and a clean voice-to-action frontend. The system is fast, resilient to phrasing variance, and easy to extend with new tools."

