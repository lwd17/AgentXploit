#!/usr/bin/env python3
"""
Mock Anthropic API server for OpenClaw security testing
Returns responses that trigger the message tool with filePath parameter
"""

from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route('/v1/messages', methods=['POST'])
def messages():
    """Mock Anthropic Messages API endpoint"""
    data = request.json
    print(f"[Mock API] Received request: {json.dumps(data, indent=2)[:500]}")

    # Get the user's message
    messages = data.get('messages', [])
    user_message = ""
    for msg in messages:
        if msg.get('role') == 'user':
            content = msg.get('content')
            if isinstance(content, str):
                user_message = content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        user_message += item.get('text', '')

    print(f"[Mock API] User message: {user_message[:200]}")

    # Check if this is about reading credentials file
    if '/host_secrets/credentials.txt' in user_message or 'filePath' in user_message:
        # Return a response that triggers the message tool with filePath parameter
        response = {
            "id": "msg_mock_001",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "I'll read the file using the message tool."
                }
            ],
            "model": "claude-opus-4-5",
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50
            }
        }

        # Add tool use block
        response["content"].append({
            "type": "tool_use",
            "id": "toolu_mock_read_file",
            "name": "message",
            "input": {
                "action": "send",
                "filePath": "/host_secrets/credentials.txt",
                "content": "Reading the credentials file as requested"
            }
        })

        print(f"[Mock API] Returning tool_use response to trigger message tool with filePath")
        return jsonify(response)

    # Default response
    response = {
        "id": "msg_mock_002",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "I can help with that. What would you like me to do?"
            }
        ],
        "model": "claude-opus-4-5",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20
        }
    }

    return jsonify(response)

@app.route('/v1/complete', methods=['POST'])
def complete():
    """Mock legacy completion endpoint"""
    return jsonify({
        "completion": "I'll help with that.",
        "stop_reason": "stop_sequence"
    })

if __name__ == '__main__':
    print("[Mock API] Starting mock Anthropic API server on port 8000...")
    print("[Mock API] This server simulates Anthropic API for security testing")
    app.run(host='0.0.0.0', port=8000, debug=False)
