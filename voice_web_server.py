import json
import tempfile
import os
import atexit
import traceback
from urllib.parse import quote
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import cgi

from main import generate_hybrid

try:
    from cactus import cactus_init, cactus_transcribe, cactus_destroy
except Exception:
    cactus_init = None
    cactus_transcribe = None
    cactus_destroy = None

WEB_DIR = Path(__file__).resolve().parent / "web"
HOST = "127.0.0.1"
PORT = 8080


def _resolve_whisper_weights():
    root = Path(__file__).resolve().parent
    candidates = [
        root / "weights" / "whisper-small",
        root.parent / "weights" / "whisper-small",
        root / "cactus" / "weights" / "whisper-small",
        root.parent / "cactus" / "weights" / "whisper-small",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return "weights/whisper-small"


WHISPER_WEIGHTS = _resolve_whisper_weights()

_WHISPER_MODEL = None

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
            },
            "required": ["location"],
        },
    },
    {
        "name": "set_alarm",
        "description": "Set an alarm for a given time",
        "parameters": {
            "type": "object",
            "properties": {
                "hour": {"type": "integer", "description": "Hour to set the alarm for"},
                "minute": {"type": "integer", "description": "Minute to set the alarm for"},
            },
            "required": ["hour", "minute"],
        },
    },
    {
        "name": "send_message",
        "description": "Send a message to a contact",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Name of the person to send the message to"},
                "message": {"type": "string", "description": "The message content to send"},
            },
            "required": ["recipient", "message"],
        },
    },
    {
        "name": "create_reminder",
        "description": "Create a reminder with a title and time",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Reminder title"},
                "time": {"type": "string", "description": "Time for the reminder (e.g. 3:00 PM)"},
            },
            "required": ["title", "time"],
        },
    },
    {
        "name": "search_contacts",
        "description": "Search for a contact by name",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name to search for"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "play_music",
        "description": "Play a song or playlist",
        "parameters": {
            "type": "object",
            "properties": {
                "song": {"type": "string", "description": "Song or playlist name"},
            },
            "required": ["song"],
        },
    },
    {
        "name": "set_timer",
        "description": "Set a countdown timer",
        "parameters": {
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "description": "Number of minutes"},
            },
            "required": ["minutes"],
        },
    },
]

_WEATHER_CODE_MAP = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
}


def _fetch_live_weather(location):
    query = quote(location.strip())
    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=1&language=en&format=json"
    with urlopen(geocode_url, timeout=6) as resp:
        geo = json.loads(resp.read().decode("utf-8"))

    results = geo.get("results") or []
    if not results:
        return f"Could not find location '{location}'."

    first = results[0]
    lat = first.get("latitude")
    lon = first.get("longitude")
    city = first.get("name", location)
    country = first.get("country", "")

    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
    )
    with urlopen(weather_url, timeout=6) as resp:
        weather = json.loads(resp.read().decode("utf-8"))

    current = weather.get("current") or {}
    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
    wind = current.get("wind_speed_10m")
    code = current.get("weather_code")
    desc = _WEATHER_CODE_MAP.get(code, "unknown conditions")
    place = f"{city}, {country}".strip().strip(",")

    return f"Current weather in {place}: {temp}°C, feels like {feels}°C, {desc}, wind {wind} km/h."


def _simulate_action(call):
    name = call.get("name", "")
    args = call.get("arguments", {})

    if name == "set_alarm":
        hour = args.get("hour")
        minute = int(args.get("minute", 0)) if str(args.get("minute", "")).isdigit() else args.get("minute")
        return f"Alarm scheduled for {hour}:{minute:02d}" if isinstance(minute, int) else f"Alarm scheduled for {hour}:{minute}"
    if name == "set_timer":
        return f"Timer set for {args.get('minutes')} minutes"
    if name == "send_message":
        return f"Message sent to {args.get('recipient')}: {args.get('message')}"
    if name == "create_reminder":
        return f"Reminder created: {args.get('title')} at {args.get('time')}"
    if name == "search_contacts":
        return f"Searching contacts for: {args.get('query')}"
    if name == "play_music":
        return f"Playing music: {args.get('song')}"
    if name == "get_weather":
        location = args.get("location")
        if not location:
            return "Weather request missing location."
        try:
            return _fetch_live_weather(str(location))
        except Exception:
            traceback.print_exc()
            return f"Unable to fetch live weather for {location} right now."
    return f"Executed {name}"


def _build_assistant_response(transcript, calls, actions, warning=None):
    if warning:
        return warning
    if not calls:
        return "I heard you, but I could not map that to available actions. Please try rephrasing."

    if len(actions) == 1:
        return f"Done. {actions[0]}."

    joined = "; ".join(actions)
    return f"Done. I processed your request: {joined}."


def _build_route_response(transcript, routed):
    raw_calls = routed.get("function_calls", [])

    def _normalize_args_for_key(arguments):
        normalized = {}
        for k, v in (arguments or {}).items():
            if isinstance(v, str):
                normalized[k] = v.strip().lower()
            else:
                normalized[k] = v
        return normalized

    calls = []
    seen = set()
    for call in raw_calls:
        key = (call.get("name", ""), json.dumps(_normalize_args_for_key(call.get("arguments", {})), sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        calls.append(call)

    actions = []
    action_seen = set()
    for call in calls:
        action = _simulate_action(call)
        if action in action_seen:
            continue
        action_seen.add(action)
        actions.append(action)

    assistant_response = _build_assistant_response(transcript, calls, actions)
    return {
        "ok": True,
        "transcript": transcript,
        "source": routed.get("source", "unknown"),
        "confidence": routed.get("confidence", 0),
        "total_time_ms": routed.get("total_time_ms", 0),
        "function_calls": calls,
        "actions": actions,
        "assistant_response": assistant_response,
    }


def _get_whisper_model():
    if not (cactus_init and cactus_transcribe and cactus_destroy):
        return None

    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = cactus_init(WHISPER_WEIGHTS)
    return _WHISPER_MODEL


@atexit.register
def _cleanup_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None and cactus_destroy:
        cactus_destroy(_WHISPER_MODEL)
        _WHISPER_MODEL = None


def _transcribe_audio_bytes(audio_bytes):
    model = _get_whisper_model()
    if model is None:
        raise RuntimeError("Whisper model unavailable. Ensure Cactus is set up with whisper weights.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        raw = cactus_transcribe(model, tmp_path)
        parsed = json.loads(raw)
        transcript = str(parsed.get("response", "")).strip()
        return transcript
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


class VoiceActionHandler(BaseHTTPRequestHandler):
    def _json_response(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, file_path):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return

        if file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        else:
            content_type = "application/octet-stream"

        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            bindings_ok = bool(cactus_init and cactus_transcribe and cactus_destroy)
            weights_path = Path(WHISPER_WEIGHTS)
            config_path = weights_path / "config.txt"
            return self._json_response(200, {
                "ok": True,
                "server": "up",
                "cactus_bindings": bindings_ok,
                "whisper_weights_path": str(weights_path),
                "whisper_weights_exists": weights_path.exists(),
                "whisper_config_exists": config_path.exists(),
            })

        if path == "/":
            return self._serve_file(WEB_DIR / "index.html")
        if path == "/app.js":
            return self._serve_file(WEB_DIR / "app.js")
        if path == "/styles.css":
            return self._serve_file(WEB_DIR / "styles.css")

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/transcribe_route":
            if "multipart/form-data" not in self.headers.get("Content-Type", ""):
                return self._json_response(400, {"ok": False, "error": "Expected multipart/form-data"})

            try:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
                )
                audio_field = form["audio"] if "audio" in form else None
                if audio_field is None or not getattr(audio_field, "file", None):
                    return self._json_response(400, {"ok": False, "error": "Missing audio file field 'audio'"})

                audio_bytes = audio_field.file.read()
                if not audio_bytes:
                    return self._json_response(400, {"ok": False, "error": "Uploaded audio is empty"})

                try:
                    transcript = _transcribe_audio_bytes(audio_bytes)
                except Exception as exc:
                    traceback.print_exc()
                    warning = f"Transcription failed: {exc}"
                    return self._json_response(200, {
                        "ok": True,
                        "transcript": "",
                        "source": "on-device",
                        "confidence": 0,
                        "total_time_ms": 0,
                        "function_calls": [],
                        "actions": [],
                        "warning": warning,
                        "assistant_response": _build_assistant_response("", [], [], warning=warning),
                    })

                if not transcript:
                    warning = "No speech detected. Please speak louder or record longer."
                    return self._json_response(200, {
                        "ok": True,
                        "transcript": "",
                        "source": "on-device",
                        "confidence": 0,
                        "total_time_ms": 0,
                        "function_calls": [],
                        "actions": [],
                        "warning": warning,
                        "assistant_response": _build_assistant_response("", [], [], warning=warning),
                    })

                messages = [{"role": "user", "content": transcript}]
                try:
                    routed = generate_hybrid(messages, TOOLS)
                    return self._json_response(200, _build_route_response(transcript, routed))
                except Exception as exc:
                    traceback.print_exc()
                    warning = f"Routing failed after transcription: {exc}"
                    return self._json_response(200, {
                        "ok": True,
                        "transcript": transcript,
                        "source": "on-device",
                        "confidence": 0,
                        "total_time_ms": 0,
                        "function_calls": [],
                        "actions": [],
                        "warning": warning,
                        "assistant_response": _build_assistant_response(transcript, [], [], warning=warning),
                    })
            except Exception as exc:
                traceback.print_exc()
                return self._json_response(400, {"ok": False, "error": f"Malformed upload: {exc}"})

        if parsed.path != "/api/route":
            return self._json_response(404, {"error": "Unknown endpoint"})

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8"))
            transcript = str(payload.get("transcript", "")).strip()
        except Exception:
            return self._json_response(400, {"error": "Invalid JSON body"})

        if not transcript:
            return self._json_response(400, {"error": "Transcript is required"})

        messages = [{"role": "user", "content": transcript}]

        try:
            routed = generate_hybrid(messages, TOOLS)
            return self._json_response(200, _build_route_response(transcript, routed))
        except Exception as exc:
            return self._json_response(500, {"ok": False, "error": str(exc)})


def main():
    if not WEB_DIR.exists():
        raise FileNotFoundError("Missing web directory. Expected ./web with index.html")

    server = ThreadingHTTPServer((HOST, PORT), VoiceActionHandler)
    print(f"Voice web app running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
