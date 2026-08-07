#!/usr/bin/env python3
"""
Mock Anthropic API server for OpenClaw path validation testing
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)

@app.route('/v1/messages', methods=['POST'])
def messages():
    """Mock Anthropic Messages API endpoint"""
    data = request.json
    print(f"[Mock API] Received request")

    response = {
        "id": "msg_mock_001",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "Mock response"
            }
        ],
        "model": "claude-opus-4-20250514",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20
        }
    }

    return jsonify(response)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("[Mock API] Starting on port 8765...")
    app.run(host='0.0.0.0', port=8765, debug=False)
