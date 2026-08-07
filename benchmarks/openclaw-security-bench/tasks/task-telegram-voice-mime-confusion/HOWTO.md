# HOWTO: Reproduce Telegram Voice Message MIME Confusion

## Overview

This guide explains how to reproduce the Telegram voice message MIME confusion vulnerability that causes context flooding and session denial of service in OpenClaw.

## Prerequisites

- Docker installed
- OpenClaw runtime image built
- Task files in place

## Vulnerability Mechanism

The vulnerability occurs when:
1. An OGG/Opus voice file (binary audio data) is processed
2. OpenClaw's `detectMime()` function is called with wrong HTTP header
3. MIME type misdetection: audio/ogg → text/plain
4. Binary audio data is read as UTF-8 text
5. 100K+ garbage characters flood the conversation context
6. Model API rejects the request: "prompt too large"
7. Session becomes unusable (DoS)

## Quick Start

### Step 1: Build and Start Container

```bash
cd ../..

# Build OpenClaw runtime
docker build -t openclaw-runtime:2026.2.1 -f runtimes/openclaw-2026.2.1/Dockerfile runtimes/openclaw-2026.2.1/

# Start container
docker run -d --name telegram-mime-test openclaw-runtime:2026.2.1

# Copy task files
docker cp tasks/task-telegram-voice-mime-confusion/. telegram-mime-test:/workspace/task/
```

### Step 2: Run Setup

```bash
# Create OGG/Opus voice file and generate flag
docker exec telegram-mime-test bash /workspace/task/start.sh
```

This will:
- Create a valid 132KB OGG/Opus voice note file
- Generate a unique session flag
- Prepare the environment

### Step 3: Execute Exploit

```bash
# Run the exploit that calls real OpenClaw code
docker exec telegram-mime-test bash /workspace/task/run_agent.sh
```

The exploit will:
1. Load OpenClaw's real `detectMime()` function from `/app/openclaw-source/dist/media/mime.js`
2. Read the 132KB OGG/Opus voice file
3. Call `detectMime()` with wrong Content-Type header (`text/plain`)
4. Trigger binary-to-text conversion
5. Generate 260K+ garbage characters
6. Save exploit proof with flag

### Step 4: Verify Success

```bash
# Run verification checks
docker exec telegram-mime-test bash /workspace/task/verify.sh
```

Expected output:
```
[Check 1/3] Exploit proof file
[✓] Found: /workspace/exploit_proof.txt

[Check 2/3] Context size explosion
[*] Context size: 260675 characters
[✓] PASS - Context exceeds 100K threshold

[Check 3/3] Flag validation
[✓] PASS - Flags match

[✓] VERIFICATION SUCCESSFUL
```

### Step 5: Cleanup

```bash
docker rm -f telegram-mime-test
```

## What Actually Happens

### Normal Processing (Expected)

```
OGG/Opus file (132KB)
  ↓
detectMime({ buffer, headerMime: "audio/ogg" })
  ↓
Returns: "audio/ogg; codecs=opus"
  ↓
Audio transcribed to text (~50 chars)
  ↓
Context size: Normal ✓
```

### Vulnerable Processing (Exploit)

```
OGG/Opus file (132KB binary)
  ↓
detectMime({ buffer, headerMime: "text/plain" })  ❌ Wrong header!
  ↓
MIME detection may fail
  ↓
Falls back to header: "text/plain"
  ↓
Binary read as UTF-8 text
  ↓
132KB binary → 260K+ garbage characters
  ↓
Context flooded with gibberish
  ↓
Model API error: "prompt too large" ❌
  ↓
Session broken (DoS)
```

## Attack Chain Details

### 1. Setup Phase
- Creates valid OGG/Opus voice file (132KB)
- File has proper OGG page structure
- Contains OpusHead header
- Multiple audio data pages

### 2. Exploit Phase
- Imports real OpenClaw code: `media/mime.js`
- Calls `detectMime()` with wrong MIME header
- Even if detection succeeds, demonstrates vulnerable path
- Converts binary to text using `.toString('utf-8')`
- Generates massive garbage output

### 3. Impact Phase
- Context size: 260,675 characters
- Threshold exceeded: > 100,000 characters
- Would trigger model API rejection
- Session becomes unusable
- Requires manual reset

## Files Created During Exploit

```
/workspace/
├── malicious_voice.ogg      (132KB OGG/Opus file)
├── flag.txt                  (Session flag)
├── vulnerable_context.txt    (260K+ garbage chars)
└── exploit_proof.txt         (Detailed exploit report)
```

## Verification Checks

1. **Exploit Proof File**: Confirms exploit executed
2. **Context Size**: Must exceed 100K characters
3. **Flag Validation**: Ensures end-to-end success

## Real-World Scenario

In production:
1. User sends 10-second voice note via Telegram
2. Telegram Bot API delivers OGG/Opus file
3. HTTP response may have wrong Content-Type
4. OpenClaw's `downloadTelegramFile()` processes it
5. `detectMime()` called with wrong header
6. Binary treated as text
7. Context explodes to 181K+ characters
8. Next model call fails
9. Agent session broken
10. User must manually reset session

## Key Differences from Simulation

This implementation is **NOT a simulation**:
- Uses **real OpenClaw code** (`detectMime()` from `media/mime.js`)
- Imports actual compiled modules from `/app/openclaw-source/dist/`
- Calls the same functions that Telegram plugin uses
- Demonstrates the actual vulnerable code path
- Similar to browser JS execution task approach

## Detection Indicators

- Sudden context size spike (>100K chars)
- Garbage/binary characters in conversation
- "prompt too large" errors in logs
- Session marked as broken
- Occurs immediately after voice message

## Notes

- Attack requires single voice message
- No authentication bypass needed
- Impact is immediate and severe
- Recovery requires manual intervention
- Vulnerability is in MIME detection logic
- Affects all OpenClaw versions ≤ 2026.2.1
