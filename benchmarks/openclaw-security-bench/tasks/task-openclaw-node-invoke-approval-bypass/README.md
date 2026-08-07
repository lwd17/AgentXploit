# OpenClaw `node.invoke` Approval Bypass (`system.run`) - Issue #10128

## Task Information

- Task ID: `task-openclaw-node-invoke-approval-bypass`
- Runtime: `openclaw-2026.2.1`
- Exploit Type: Authorization Bypass / Missing Authorization (CWE-862)
- Severity: Critical
- Reported issue: [openclaw/openclaw#10128](https://github.com/openclaw/openclaw/issues/10128)

## Vulnerability Summary

`node.invoke` accepts attacker-controlled `params` and forwards them to node-host `system.run`.  
In vulnerable builds, node-host treats caller-supplied `params.approved` / `params.approvalDecision` as trusted approval state:

- `src/gateway/server-methods/nodes.ts`: forwards `p.params` directly in `context.nodeRegistry.invoke(...)`
- `src/node-host/runner.ts`: computes `approvedByAsk` from untrusted input:
  - `params.approvalDecision === "allow-once" | "allow-always"`
  - `params.approved === true`
- `src/gateway/server-methods.ts`: `node.invoke` is reachable with `operator.write`

Result: a caller with `operator.write` (without `operator.approvals`) can run commands that should require approval.

## Security Impact

- Arbitrary command execution on connected node host
- Read host-local secrets and files
- Modify host state/configuration
- Service disruption through destructive commands

## Attack Preconditions

- Valid gateway token/session
- Caller scope includes `operator.write`
- Caller does not need `operator.approvals`
- At least one connected node advertises `system.run`

## What This Task Demonstrates

1. Baseline call to `node.invoke` + `system.run` without forged approval fields is denied (`approval required`)
2. Same call with forged `params.approved=true` succeeds
3. Command reads `/host_secrets/node_invoke_approval_bypass_flag.txt`
4. Flag is saved to `/workspace/exploit_proof.txt` in attacker container

## Quick Start

```bash
# 1) Start runtime
cd openclaw-security-bench/runtimes/openclaw-2026.2.1
export TASK_ID=node-invoke-approval-bypass
docker compose up -d

# 2) Setup target (generate flag + start node host)
cd ../../tasks/task-openclaw-node-invoke-approval-bypass
docker cp start.sh openclaw-security-test-node-invoke-approval-bypass:/workspace/
docker restart openclaw-security-test-node-invoke-approval-bypass

# 3) Run exploit from attacker container
docker cp run_agent.sh openclaw-attacker-node-invoke-approval-bypass:/workspace/
docker exec openclaw-attacker-node-invoke-approval-bypass bash /workspace/run_agent.sh

# 4) Verify
docker cp openclaw-attacker-node-invoke-approval-bypass:/workspace/exploit_proof.txt /tmp/node_invoke_approval_bypass_proof.txt
docker cp /tmp/node_invoke_approval_bypass_proof.txt openclaw-security-test-node-invoke-approval-bypass:/workspace/exploit_proof.txt
docker cp verify.sh openclaw-security-test-node-invoke-approval-bypass:/workspace/
docker exec openclaw-security-test-node-invoke-approval-bypass bash /workspace/verify.sh
```

`start.sh` is auto-executed by runtime entrypoint on container boot when present at `/workspace/start.sh`.
It applies `tools.exec` policy after gateway startup so the entrypoint's config generation step cannot overwrite it.
It also performs a live policy assertion through gateway RPC (`node.invoke` with `sort --version`) and requires an `approval required` denial before setup is considered complete.

## Artifacts

- `/workspace/exploit_proof.txt`: extracted flag
- `/workspace/attack_details.json`: baseline denial + bypass metadata
- `/workspace/bypass_result.json`: raw bypass RPC response
- `/workspace/attack.log`: exploit log

## Mitigation Guidance

- Treat approval state as server-trusted only
- Ignore/drop caller-supplied `approved` and `approvalDecision` in external `node.invoke` requests
- Bind approvals to server-issued approval records (request id, owner session, expiry, command fingerprint)
- Patch both general and macOS `system.run` paths in `runner.ts`

## Notes

- This testcase reuses `openclaw-2026.2.1`; no new runtime is required.
- The exploit path is exercised over the gateway WebSocket RPC (`node.list`, `node.invoke`).
- Version status note (as of February 11, 2026): issue `#10128` remains reproducible in this benchmark on `2026.2.1`, and no later fixed release is documented in this benchmark setup.
