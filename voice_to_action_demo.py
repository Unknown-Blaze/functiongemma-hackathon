import json
from pathlib import Path

from main import generate_hybrid

try:
    from cactus import cactus_init, cactus_transcribe, cactus_destroy
except Exception:
    cactus_init = None
    cactus_transcribe = None
    cactus_destroy = None


TOOLS = [
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
                "recipient": {"type": "string", "description": "Name of contact"},
                "message": {"type": "string", "description": "Message body"},
            },
            "required": ["recipient", "message"],
        },
    },
]


def execute_tool(call):
    name = call.get("name")
    args = call.get("arguments", {})
    if name == "set_alarm":
        print(f"[ACTION] Alarm scheduled for {args.get('hour')}:{int(args.get('minute', 0)):02d}")
    elif name == "send_message":
        print(f"[ACTION] Message sent to {args.get('recipient')}: {args.get('message')}")
    else:
        print(f"[ACTION] Unknown tool: {name} {args}")


def transcribe_audio(audio_path: Path):
    if not cactus_init:
        raise RuntimeError("Cactus Python bindings unavailable in this environment")

    whisper_model = cactus_init("weights/whisper-small")
    try:
        result = json.loads(cactus_transcribe(whisper_model, str(audio_path)))
        return result.get("response", "").strip()
    finally:
        cactus_destroy(whisper_model)


def main():
    audio = Path("sample.wav")
    if not audio.exists():
        raise FileNotFoundError("Expected sample.wav in current directory")

    transcript = transcribe_audio(audio)
    print(f"Transcript: {transcript}")

    messages = [{"role": "user", "content": transcript}]
    routed = generate_hybrid(messages, TOOLS)
    print(f"Route source: {routed.get('source')} | confidence={routed.get('confidence', 0):.3f}")

    for call in routed.get("function_calls", []):
        execute_tool(call)


if __name__ == "__main__":
    main()
