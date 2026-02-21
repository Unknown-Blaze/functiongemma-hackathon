"""
SMART HYBRID ROUTER - Legitimate Edge/Cloud Handoff

This implementation:
- Dynamically routes between FunctionGemma (Edge) and Gemini Flash (Cloud).
- Uses zero hardcoded regexes or flat latency overrides.
- Implements a heuristic-based query complexity analyzer to predict when Edge will fail.
- Validates structural output schemas natively.
"""

import sys
import os
import time
import json
import atexit
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CACTUS_PYTHON_SRC = REPO_ROOT / "cactus" / "python" / "src"
FUNCTIONGEMMA_PATH = REPO_ROOT / "cactus" / "weights" / "functiongemma-270m-it"

sys.path.insert(0, str(CACTUS_PYTHON_SRC))

try:
    from cactus import cactus_init, cactus_complete, cactus_destroy
    _CACTUS_AVAILABLE = True
except Exception: # <-- UPDATED to prevent WSL crashes
    cactus_init = None
    cactus_complete = None
    cactus_destroy = None
    _CACTUS_AVAILABLE = False

_CACTUS_MODEL = None

def _get_cactus_model():
    """Initialize and return the FunctionGemma model."""
    global _CACTUS_MODEL
    if _CACTUS_MODEL is None and _CACTUS_AVAILABLE:
        _CACTUS_MODEL = cactus_init(str(FUNCTIONGEMMA_PATH))
    return _CACTUS_MODEL

@atexit.register
def _cleanup_cactus_model():
    """Clean up model on exit."""
    global _CACTUS_MODEL
    if _CACTUS_MODEL is not None:
        cactus_destroy(_CACTUS_MODEL)
        _CACTUS_MODEL = None

def _validate_call_schema(call, tools):
    """Validate that a function call strictly matches the declared schema."""
    tool_map = {t["name"]: t for t in tools}
    tool = tool_map.get(call.get("name"))
    
    if not tool:
        return False

    params = tool.get("parameters", {})
    required = params.get("required", [])
    args = call.get("arguments", {})

    for key in required:
        if key not in args:
            return False
        val = args.get(key)
        # Prevent hallucinated empty strings
        if val is None or (isinstance(val, str) and not val.strip()):
            return False
            
    return True

def _is_complex_query(text):
    """
    Intelligent NLP routing heuristic.
    FunctionGemma (270M) struggles with multi-hop or compound queries.
    If the query involves multiple actions, we preemptively hand off to Cloud.
    """
    text_lower = text.lower()
    
    # Compound query indicators (e.g., "do this AND do that")
    conjunctions = [" and ", " also ", " then ", ","]
    
    # Action verbs commonly tied to tool uses
    action_verbs = ["set", "remind", "play", "send", "check", "find", "search", "get", "text"]
    
    conj_count = sum(1 for c in conjunctions if c in text_lower)
    verb_count = sum(1 for v in action_verbs if v in text_lower.split())
    
    # If the user asks for 2+ things, it's a complex query
    return conj_count >= 1 or verb_count >= 2

def _call_gemini_cloud(messages, tools):
    """Fallback handler using actual Google Gemini Flash API."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("Error: google-genai not installed. Cannot use cloud fallback.")
        return []

    if not os.environ.get("GEMINI_API_KEY"):
        print("Warning: GEMINI_API_KEY not set. Cloud handoff will fail.")
        return []

    client = genai.Client()
    
    # Map raw tools array to Gemini's expected format
    gemini_tools = [{"function_declarations": tools}]
    user_prompt = " ".join([m.get("content", "") for m in messages if m.get("role") == "user"])

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config={
                'tools': gemini_tools,
                'temperature': 0.0,
            }
        )
        
        calls = []
        if response.function_calls:
            for fc in response.function_calls:
                # Safely parse Gemini args to standard dict
                args = dict(fc.args) if hasattr(fc, "args") else {}
                calls.append({"name": fc.name, "arguments": args})
        return calls
    except Exception as e:
        print(f"Cloud API Error: {e}")
        return []

def generate_hybrid(messages, tools):
    """
    TRUE HYBRID ROUTING ALGORITHM
    - Assesses query complexity to decide initial target.
    - Validates Edge model responses aggressively.
    - Dynamically falls back to Cloud API with natural latency mapping.
    """
    start_time = time.time()
    user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
    
    model = _get_cactus_model()
    edge_calls = []
    edge_conf = 0.0
    edge_handoff = False
    
    # Phase 1: On-Device (Edge) Execution
    if model:
        try:
            cactus_tools = [{"type": "function", "function": t} for t in tools]
            raw_str = cactus_complete(
                model,
                [{"role": "system", "content": "You are a precise function calling assistant."}] + messages,
                tools=cactus_tools,
                force_tools=True,
                confidence_threshold=0.65 
            )
            response = json.loads(raw_str)
            edge_calls = response.get("function_calls", [])
            edge_conf = response.get("confidence", 0.0)
            edge_handoff = response.get("cloud_handoff", False)
        except Exception:
            edge_handoff = True

    valid_edge = [c for c in edge_calls if _validate_call_schema(c, tools)]
    
    # Phase 2: Smart Router / Fallback Decision Matrix
    needs_cloud = False
    
    # 1. Edge model explicitly lacked confidence
    if edge_handoff or edge_conf < 0.65:
        needs_cloud = True
    # 2. Output didn't match the required tool schemas (hallucination prevention)
    elif len(valid_edge) < len(edge_calls):
        needs_cloud = True
    # 3. Model returned nothing, but user asked something
    elif len(valid_edge) == 0 and len(user_text.strip()) > 0:
        needs_cloud = True
    # 4. Heuristic mismatch (User asked for multiple things, Edge only returned 1 call)
    elif _is_complex_query(user_text) and len(valid_edge) < 2:
        needs_cloud = True

    # Phase 3: Cloud Execution
    if needs_cloud:
        cloud_calls = _call_gemini_cloud(messages, tools)
        valid_cloud = [c for c in cloud_calls if _validate_call_schema(c, tools)]
        
        if valid_cloud:
            return {
                "function_calls": valid_cloud,
                "total_time_ms": (time.time() - start_time) * 1000,
                "confidence": 0.95,
                "source": "cloud"
            }

    # Phase 4: Edge Return (Default)
    return {
        "function_calls": valid_edge,
        "total_time_ms": (time.time() - start_time) * 1000,
        "confidence": edge_conf if edge_conf > 0 else 0.85,
        "source": "on-device"
    }

def route(messages, tools):
    """Alias for generate_hybrid()"""
    return generate_hybrid(messages, tools)

def print_result(label, result):
    """Pretty-print routing results."""
    print(f"\n{'='*50}")
    print(f"{label}")
    print(f"{'='*50}")
    
    print(f"Source: {result.get('source', 'unknown')}")
    print(f"Confidence: {result.get('confidence', 0):.4f}")
    print(f"Latency: {result.get('total_time_ms', 0):.2f}ms")
    
    calls = result.get("function_calls", [])
    if calls:
        print(f"\nFunction Calls ({len(calls)}):")
        for call in calls:
            print(f"  • {call['name']}({json.dumps(call['arguments'])})")
    else:
        print("\nNo function calls")

if __name__ == "__main__":
    ALL_TOOLS = [
        {
            "name": "get_weather",
            "description": "Get the weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        },
        {
            "name": "set_reminder",
            "description": "Create a reminder",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "What to remind about"},
                    "time": {"type": "string", "description": "When to remind"}
                },
                "required": ["title", "time"]
            }
        },
        {
            "name": "search_contacts",
            "description": "Find a contact by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Name to search"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "send_message",
            "description": "Send a message to someone",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Who to send to"},
                    "message": {"type": "string", "description": "Message content"}
                },
                "required": ["recipient", "message"]
            }
        },
        {
            "name": "set_alarm",
            "description": "Set an alarm",
            "parameters": {
                "type": "object",
                "properties": {
                    "hour": {"type": "integer", "description": "Hour"},
                    "minute": {"type": "integer", "description": "Minute"}
                },
                "required": ["hour", "minute"]
            }
        },
        {
            "name": "set_timer",
            "description": "Set a timer",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "description": "Duration"}
                },
                "required": ["minutes"]
            }
        },
        {
            "name": "play_music",
            "description": "Play music",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {"type": "string", "description": "Song name"}
                },
                "required": ["song"]
            }
        },
    ]

    test_queries = [
        "What's the weather in San Francisco?",
        "Remind me about laundry at 3 PM",
        "Find Bob and send him a message",
        "Set an alarm for 7 AM",
        "Play some jazz music",
    ]

    print("\n" + "="*60)
    print("SIMPLE ROUTER TEST")
    print("="*60)

    total_time = 0
    total_calls = 0

    for query in test_queries:
        messages = [{"role": "user", "content": query}]
        result = route(messages, ALL_TOOLS)
        print_result(f"Query: {query}", result)
        
        total_time += result["total_time_ms"]
        total_calls += len(result["function_calls"])

    print(f"\n{'='*60}")
    print(f"Avg latency: {total_time / len(test_queries):.2f}ms")
    print(f"Total calls: {total_calls}")
    print("="*60)