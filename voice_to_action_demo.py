"""
Voice-to-Action Demo: End-to-end proof-of-concept for Rubric 3 (low-latency voice-to-action).

Usage:
  python voice_to_action_demo.py                          # Simulate with test queries
  python voice_to_action_demo.py --audio sample.wav       # Test with actual audio file
  python voice_to_action_demo.py --audio sample.wav --verbose  # Detailed latency breakdown

Features:
  - Stage-by-stage latency measurement (transcription, routing, execution)
  - Simulation mode for testing without audio (uses benchmark queries)
  - Structured output for benchmarking and judging
  - Full tool support from benchmark.py
"""

import json
import time
import argparse
from pathlib import Path

from main import generate_hybrid
from benchmark import (
    TOOL_GET_WEATHER, TOOL_SET_ALARM, TOOL_SEND_MESSAGE, TOOL_CREATE_REMINDER,
    TOOL_SEARCH_CONTACTS, TOOL_PLAY_MUSIC, TOOL_SET_TIMER
)

try:
    from cactus import cactus_init, cactus_transcribe, cactus_destroy
    _CACTUS_AVAILABLE = True
except Exception:
    cactus_init = None
    cactus_transcribe = None
    cactus_destroy = None
    _CACTUS_AVAILABLE = False


# Full tool set (consistent with benchmark.py)
ALL_TOOLS = [
    TOOL_GET_WEATHER,
    TOOL_SET_ALARM,
    TOOL_SEND_MESSAGE,
    TOOL_CREATE_REMINDER,
    TOOL_SEARCH_CONTACTS,
    TOOL_PLAY_MUSIC,
    TOOL_SET_TIMER,
]

# Sample queries for simulation mode
SAMPLE_QUERIES = [
    "What is the weather in San Francisco?",
    "Set an alarm for 10 AM.",
    "Send a message to Alice saying good morning.",
    "Find Bob in my contacts and text him a reminder for the meeting at 3 PM.",
    "Play some jazz music.",
    "Set a timer for 5 minutes.",
    "Remind me about the meeting at 3:00 PM.",
]


def execute_tool(call):
    """Simulate tool execution and return result."""
    name = call.get("name")
    args = call.get("arguments", {})
    
    results = {
        "get_weather": f"Weather in {args.get('location', 'unknown')}: Sunny, 72°F",
        "set_alarm": f"Alarm set for {args.get('hour', 0)}:{int(args.get('minute', 0)):02d}",
        "send_message": f"Message sent to {args.get('recipient', 'unknown')}: '{args.get('message', '')}'",
        "create_reminder": f"Reminder created: '{args.get('title', 'unknown')}' at {args.get('time', 'unknown')}",
        "search_contacts": f"Found contact: {args.get('query', 'unknown')}",
        "play_music": f"Now playing: {args.get('song', 'unknown')}",
        "set_timer": f"Timer set for {args.get('minutes', 0)} minutes",
    }
    
    return results.get(name, f"Unknown tool: {name}")


def transcribe_audio(audio_path: Path):
    """Transcribe audio file using on-device Whisper."""
    if not _CACTUS_AVAILABLE:
        raise RuntimeError("Cactus Python bindings not available. Install cactus package.")
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    try:
        whisper_model = cactus_init("../cactus/weights/whisper-small")
        if whisper_model is None:
            raise RuntimeError("Failed to initialize Whisper model. Check weights path.")
        
        start = time.time()
        result_str = cactus_transcribe(whisper_model, str(audio_path))
        elapsed = (time.time() - start) * 1000
        
        try:
            result = json.loads(result_str)
            text = result.get("response", "").strip()
        except json.JSONDecodeError:
            text = result_str.strip()
        
        return text, elapsed
    finally:
        if whisper_model is not None:
            cactus_destroy(whisper_model)


def route_and_execute(transcript, tools, verbose=False):
    """Route transcript to tool calls and execute."""
    # Stage: Routing
    messages = [{"role": "user", "content": transcript}]
    start = time.time()
    routed = generate_hybrid(messages, tools)
    route_time = (time.time() - start) * 1000
    
    # Execution
    start = time.time()
    results = []
    for call in routed.get("function_calls", []):
        result = execute_tool(call)
        results.append({"tool": call["name"], "result": result})
    exec_time = (time.time() - start) * 1000
    
    return {
        "transcript": transcript,
        "calls": routed.get("function_calls", []),
        "source": routed.get("source", "unknown"),
        "confidence": routed.get("confidence", 0.0),
        "routing_time_ms": route_time,
        "execution_time_ms": exec_time,
        "model_time_ms": routed.get("total_time_ms", 0),
        "results": results,
        "verbose": {
            "routing_details": routed,
        } if verbose else None,
    }


def print_result(result, transcribe_time_ms=None, verbose=False):
    """Pretty-print result with latency breakdown."""
    print("\n" + "="*70)
    print("VOICE-TO-ACTION RESULT")
    print("="*70)
    
    # Input
    print(f"\n📝 Input (Transcript):")
    print(f"  {result['transcript']}")
    
    # Routing
    print(f"\n🔀 Routing:")
    print(f"  Source: {result['source']}")
    print(f"  Confidence: {result['confidence']:.4f}")
    print(f"  Calls: {len(result['calls'])}")
    for call in result['calls']:
        print(f"    - {call['name']}({json.dumps(call.get('arguments', {}))})")
    
    # Execution
    print(f"\n⚡ Execution:")
    if result['results']:
        for r in result['results']:
            print(f"  [{r['tool']}] {r['result']}")
    else:
        print(f"  (no function calls to execute)")
    
    # Latency Breakdown
    print(f"\n⏱️  Latency Breakdown:")
    total = 0
    if transcribe_time_ms is not None:
        print(f"  Transcription (Whisper): {transcribe_time_ms:.1f}ms")
        total += transcribe_time_ms
    print(f"  Routing (Hybrid Router): {result['routing_time_ms']:.1f}ms")
    total += result['routing_time_ms']
    print(f"  Execution: {result['execution_time_ms']:.1f}ms")
    total += result['execution_time_ms']
    print(f"  ─────────────────────────────")
    print(f"  TOTAL: {total:.1f}ms")
    
    if verbose and result['verbose']:
        print(f"\n🔧 Verbose (Routing Details):")
        details = result['verbose']['routing_details']
        print(f"  Model time: {details.get('total_time_ms', 0):.1f}ms")
        print(f"  On-device: {details.get('source', 'unknown')}")
    
    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Voice-to-Action Demo: End-to-end voice command execution.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with sample queries (simulation mode)
  python voice_to_action_demo.py

  # Test with actual audio file
  python voice_to_action_demo.py --audio sample.wav

  # Show detailed latency breakdown
  python voice_to_action_demo.py --audio sample.wav --verbose

  # Test with custom audio directory
  python voice_to_action_demo.py --audio ../assets/voice_samples/command.wav
        """,
    )
    parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="Path to audio file (.wav). If not provided, simulates with sample queries.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed latency breakdown and routing information.",
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("VOICE-TO-ACTION PROOF-OF-CONCEPT (Rubric 3)")
    print("="*70)
    
    if args.audio:
        # ===== REAL AUDIO MODE =====
        if not _CACTUS_AVAILABLE:
            print("\n❌ ERROR: Cactus not available. Cannot transcribe audio.")
            print("   Run in simulation mode instead: python voice_to_action_demo.py")
            return
        
        print(f"\n🎙️  Audio Mode: {args.audio}")
        audio_path = Path(args.audio)
        
        try:
            print(f"   Loading audio...")
            transcript, transcribe_time = transcribe_audio(audio_path)
            print(f"   ✓ Transcribed ({transcribe_time:.1f}ms)")
            
            result = route_and_execute(transcript, ALL_TOOLS, verbose=args.verbose)
            print_result(result, transcribe_time_ms=transcribe_time, verbose=args.verbose)
        except FileNotFoundError as e:
            print(f"\n❌ ERROR: {e}")
            print("\n💡 TIP: Place audio file in current directory or specify full path.")
            print(f"   Example: python voice_to_action_demo.py --audio /path/to/sample.wav")
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        # ===== SIMULATION MODE =====
        print(f"\n🧪 Simulation Mode: Testing with {len(SAMPLE_QUERIES)} sample queries")
        print("   (Use --audio flag to test with real audio)\n")
        
        total_latency = 0
        success_count = 0
        
        for i, query in enumerate(SAMPLE_QUERIES, 1):
            print(f"\n[{i}/{len(SAMPLE_QUERIES)}] Query: {query}")
            try:
                result = route_and_execute(query, ALL_TOOLS, verbose=False)
                
                # Quick summary
                status = "✓" if result['calls'] else "✗"
                print(f"  {status} {len(result['calls'])} calls | "
                      f"{result['routing_time_ms']:.1f}ms | "
                      f"{result['source']}")
                
                total_latency += result['routing_time_ms']
                success_count += 1
            except Exception as e:
                print(f"  ✗ ERROR: {e}")
        
        print(f"\n{'='*70}")
        print(f"SIMULATION SUMMARY")
        print(f"{'='*70}")
        print(f"Queries tested: {len(SAMPLE_QUERIES)}")
        print(f"Successful: {success_count}/{len(SAMPLE_QUERIES)}")
        print(f"Avg latency: {total_latency/len(SAMPLE_QUERIES):.1f}ms")
        print(f"Total time: {total_latency:.1f}ms")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
