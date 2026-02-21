"""
Hybrid Router REST API Server for Mobile & Web Clients

Usage:
  python api_server.py                    # Run on localhost:5000
  python api_server.py --host 0.0.0.0    # Listen on all interfaces
  python api_server.py --port 8080        # Custom port

Android client will call:
  POST http://<your-ip>:5000/route
  Content-Type: application/json
  {
    "messages": [{"role": "user", "content": "..."}],
    "tools": [...]
  }

Response:
  {
    "function_calls": [...],
    "confidence": 0.95,
    "source": "on-device",
    "total_time_ms": 15.2
  }
"""

import json
import argparse
import sys
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

# Import router
from main import generate_hybrid
from benchmark import (
    TOOL_GET_WEATHER, TOOL_SET_ALARM, TOOL_SEND_MESSAGE, TOOL_CREATE_REMINDER,
    TOOL_SEARCH_CONTACTS, TOOL_PLAY_MUSIC, TOOL_SET_TIMER
)

app = Flask(__name__)
CORS(app)  # Enable CORS for mobile clients

# All tools from benchmark
ALL_TOOLS = [
    TOOL_GET_WEATHER,
    TOOL_SET_ALARM,
    TOOL_SEND_MESSAGE,
    TOOL_CREATE_REMINDER,
    TOOL_SEARCH_CONTACTS,
    TOOL_PLAY_MUSIC,
    TOOL_SET_TIMER,
]


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "Hybrid Router API",
        "version": "1.0",
    })


@app.route('/tools', methods=['GET'])
def get_tools():
    """Return available tools (for UI initialization)."""
    return jsonify({
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
            }
            for t in ALL_TOOLS
        ]
    })


@app.route('/route', methods=['POST'])
def route():
    """
    Main routing endpoint.
    
    Request:
    {
        "messages": [
            {"role": "user", "content": "What's the weather in SF?"}
        ],
        "tools": [...]  # Optional; defaults to ALL_TOOLS
    }
    
    Response:
    {
        "function_calls": [
            {
                "name": "get_weather",
                "arguments": {"location": "San Francisco"}
            }
        ],
        "confidence": 0.98,
        "source": "on-device",
        "total_time_ms": 2.1,
        "status": "success"
    }
    """
    try:
        data = request.get_json()
        
        # Validate input
        if not data:
            return jsonify({
                "status": "error",
                "error": "Empty request body"
            }), 400
        
        messages = data.get("messages")
        if not messages:
            return jsonify({
                "status": "error",
                "error": "Missing 'messages' field"
            }), 400
        
        # Use provided tools or default to ALL_TOOLS
        tools = data.get("tools", ALL_TOOLS)
        
        # Call router
        result = generate_hybrid(messages, tools)
        
        # Return result
        return jsonify({
            "status": "success",
            "function_calls": result.get("function_calls", []),
            "confidence": result.get("confidence", 0.0),
            "source": result.get("source", "unknown"),
            "total_time_ms": result.get("total_time_ms", 0.0),
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/route/batch', methods=['POST'])
def route_batch():
    """
    Batch routing endpoint (for testing multiple queries).
    
    Request:
    {
        "queries": [
            "What's the weather in SF?",
            "Set an alarm for 10 AM",
            ...
        ]
    }
    
    Response:
    {
        "results": [
            {
                "query": "...",
                "function_calls": [...],
                "confidence": 0.98,
                ...
            },
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        queries = data.get("queries", [])
        
        if not queries:
            return jsonify({
                "status": "error",
                "error": "Missing 'queries' field"
            }), 400
        
        results = []
        for query in queries:
            messages = [{"role": "user", "content": query}]
            result = generate_hybrid(messages, ALL_TOOLS)
            results.append({
                "query": query,
                "function_calls": result.get("function_calls", []),
                "confidence": result.get("confidence", 0.0),
                "source": result.get("source", "unknown"),
                "total_time_ms": result.get("total_time_ms", 0.0),
            })
        
        return jsonify({
            "status": "success",
            "results": results
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/', methods=['GET'])
def index():
    """API documentation."""
    return jsonify({
        "service": "Hybrid Router API",
        "version": "1.0",
        "endpoints": {
            "GET /health": "Health check",
            "GET /tools": "List available tools",
            "POST /route": "Route a user query to function calls",
            "POST /route/batch": "Route multiple queries",
        },
        "example": {
            "url": "POST /route",
            "body": {
                "messages": [
                    {"role": "user", "content": "What's the weather in San Francisco?"}
                ]
            },
            "response": {
                "status": "success",
                "function_calls": [
                    {
                        "name": "get_weather",
                        "arguments": {"location": "San Francisco"}
                    }
                ],
                "confidence": 0.98,
                "source": "on-device",
                "total_time_ms": 2.1
            }
        },
        "docs": "See README for full documentation"
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hybrid Router API Server')
    parser.add_argument('--host', type=str, default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"\n{'='*70}")
    print("HYBRID ROUTER API SERVER")
    print(f"{'='*70}")
    print(f"Starting server on http://{args.host}:{args.port}")
    print(f"Health check: http://{args.host}:{args.port}/health")
    print(f"API docs: http://{args.host}:{args.port}/")
    print(f"{'='*70}\n")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
