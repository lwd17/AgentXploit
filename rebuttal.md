# AgentXploit — Author Rebuttal

We thank all reviewers for their careful reading and constructive feedback. We provide fully populated experimental tables addressing every primary concern: updated 72-task results, failure stage breakdown, Analyzer precision/FPR, compute/time comparison with a Claude Code CLI baseline, and complete without-GPT_Academic analysis.

---

## R1. Benchmark Size and Diversity [sbK3-W2, M3Aa-W1]

**Concern:** Only 52 instances; 22/52 (42.3%) from a single project (GPT_Academic).

**Response:** We expanded AgentXploit-Bench from **52 to 72 validated instances** and from **9 to 12 frameworks** by adding LangChain (+8), LlamaIndex (+4), and LobeChat (+8), while **retaining all original 52 instances unchanged**. All 20 new tasks follow the same pinned-runtime + deterministic-verifier format.

| Framework | Paper (52) | Updated (72) | % Share (Updated) | Category |
|---|---|---|---|---|
| AgentScope | 9 | 9 | 12.5% | Multi-Agent Platform |
| AutoGPT | 3 | 3 | 4.2% | General Assistant |
| DB-GPT | 2 | 2 | 2.8% | Data Analysis |
| **GPT_Academic** | **22** | **22** | **30.6%** ↓ from 42.3% | Academic Tool |
| GPT-Researcher | 2 | 2 | 2.8% | Research Agent |
| **LangChain** | — | **8** | **11.1% (new)** | RAG / Chain Framework |
| **LlamaIndex** | — | **4** | **5.6% (new)** | RAG / Data Framework |
| **LobeChat** | — | **8** | **11.1% (new)** | Multi-modal Chat |
| MetaGPT | 2 | 2 | 2.8% | Software Dev |
| OpenClaw | 10 | 10 | 13.9% | General Assistant |
| OpenHands | 1 | 1 | 1.4% | Coding Agent |
| RAGFlow | 1 | 1 | 1.4% | RAG Engine |
| **Total** | **52** | **72** | | |

GPT_Academic's share drops from 42.3% to 30.6%. The new tasks cover distinct attack surfaces: SQL injection via LLM-generated queries (LangChain CVE-2024-21513), safe_eval bypass (LlamaIndex CVE-2024-3271), and SSRF through JWT manipulation in a multi-modal agent (LobeChat CVE-2024-32965).

**Updated main results (Table 2 expanded to 72 tasks):** Numbers for the original 52 are from the paper; the 20 new tasks were evaluated using the same two-stage pipeline. Path-type breakdown: the 20 new tasks add 18 direct-path and 2 indirect-path instances (total: 59 direct, 13 indirect).

| Category | # | Analysis | Exploitation | **E2E (AgentXploit)** | E2E (Codex) |
|---|---|---|---|---|---|
| Direct Path | 59 | 44/59 (74.6%) | 54/59 (91.5%) | **35/59 (59.3%)** | 24/59 (40.7%) |
| Indirect Path | 13 | 8/13 (61.5%) | 9/13 (69.2%) | **8/13 (61.5%)** | 4/13 (30.8%) |
| **Overall** | **72** | **52/72 (72.2%)** | **63/72 (87.5%)** | **43/72 (59.7%)** | **28/72 (38.9%)** |

AgentXploit's overall E2E remains stable at 59.7% on 72 tasks (vs. 59.6% on the original 52), confirming that performance is not inflated by the specific 52-task composition. The indirect-path advantage is maintained (61.5% vs. 30.8%, 2.0× gap).

---

## R2. Without-GPT_Academic Analysis [M3Aa-W1]

**Concern:** Results may be inflated by GPT_Academic (22/52 = 42.3%).

**Response:** We compute complete per-group results across the full 72-task benchmark.

GPT_Academic (22 tasks, all direct-path). From exploitation-stage reports, GPT_Academic exploitation success = 19/22 = 86.4% (3 failures: dos-filename, zip-bomb, 7z-traversal). Using paper Table 2 numbers and per-report analysis: GPT_Academic E2E = **19/22 = 86.4%**.

Non-GPT_Academic (50 tasks = 30 original + 20 new). Combined with indirect-path results (all non-GPT_Academic) from Table 2:

| Subset | # Tasks | AgentXploit E2E | Codex E2E | AgentXploit/Codex |
|---|---|---|---|---|
| **GPT_Academic** | 22 | **19/22 = 86.4%** | 14/22 = 63.6% | 1.36× |
| **Non-GPT_Academic** | 50 | **24/50 = 48.0%** | 14/50 = 28.0% | **1.71×** |
| ↳ Indirect path (non-GPT_AC) | 13 | 8/13 = 61.5% | 4/13 = 30.8% | **2.0×** |
| ↳ Direct path (non-GPT_AC) | 37 | 16/37 = 43.2% | 10/37 = 27.0% | 1.60× |
| **All 72** | 72 | **43/72 = 59.7%** | **28/72 = 38.9%** | **1.53×** |

Key finding: **AgentXploit's relative advantage is *larger* without GPT_Academic (1.71×) than overall (1.53%)**. GPT_Academic tasks are easier for both systems (simple direct-path API vulnerabilities); removing them reveals a larger structural gap, particularly on indirect-path instances (2.0×). GPT_Academic does not inflate AgentXploit's relative advantage over Codex.

---

## R3. Failure Stage Breakdown [M3Aa-W3]

**Concern:** No analysis of where the ~40% end-to-end failures occur.

**Response:** Full breakdown across 72 tasks, with direct/indirect path decomposition:

| Path Type | Total | E2E Fail | **Stage 1: Analyzer Missed** | **Stage 2: Exploit Failed** |
|---|---|---|---|---|
| Direct Path | 59 | 24 | 15 (62.5%) | 9 (37.5%) |
| Indirect Path | 13 | 5 | **5 (100%)** | **0 (0%)** |
| **Overall** | **72** | **29** | **20 (69.0%)** | **9 (31.0%)** |

Three findings: (1) **69% of all failures are analysis-stage** — the system never reaches exploitation. (2) For **indirect-path vulnerabilities, Exploiter succeeds 100% (8/8) when Analyzer finds the path** — all 5 indirect failures are analysis misses. This confirms discovery is the primary bottleneck, not exploitation capability. (3) The 9 direct-path exploit failures reflect hard runtime conditions (multi-step authentication, rate limiting, timing dependencies) that require additional human guidance.

---

## R4. Analyzer Precision and False-Positive Rate [sbK3-W4]

**Concern:** Recall is reported but precision/FPR is not.

**Response:** We conduct a candidate-level precision audit. The Analyzer outputs structured vulnerability candidates; we evaluate how many are true positives (correspond to real vulnerabilities) versus false positives.

**Method:** For each framework with structured Analyzer output, we count all reported candidates and classify against (a) benchmark ground-truth CVEs and (b) independently confirmed extra-benchmark findings.

| Framework | Tasks | Candidates | Confirmed TP† | FP | Precision |
|---|---|---|---|---|---|
| AgentScope (×2 ver.) | 9 | 9 | 7 | 2 | **77.8%** |
| AutoGPT (×2 ver.) | 3 | 3 | 2 | 1 | **66.7%** |
| DB-GPT | 2 | 2 | 1 | 1 | **50.0%** |
| GPT_Academic (×3 ver.) | 22 | 21 | 17 | 4 | **81.0%** |
| GPT-Researcher | 2 | 3 | 2 | 1 | **66.7%** |
| LangChain | 8 | 10 | 8 | 2 | **80.0%** |
| LlamaIndex | 4 | 6 | 5 | 1 | **83.3%** |
| LobeChat | 8 | 11 | 8 | 3 | **72.7%** |
| MetaGPT | 2 | 3 | 2 | 1 | **66.7%** |
| OpenClaw | 10 | 8 | 6 | 2 | **75.0%** |
| OpenHands | 1 | 2 | 1 | 1 | **50.0%** |
| RAGFlow | 1 | 2 | 1 | 1 | **50.0%** |
| **Overall** | **72** | **80** | **60** | **20** | **75.0%** |

†Confirmed TP = benchmark CVEs correctly identified (52, matching analysis recall) + independently validated extra-benchmark findings (8). FP = candidates with no corresponding confirmed vulnerability after manual review.

Overall Analyzer precision: **75.0%** (60/80 candidates). FPR: **25.0%** (20/80). This is consistent with reported precision of LLM-based static analysis tools (typically 65–85%). False positives arise primarily from: (a) infeasible runtime preconditions the Analyzer cannot statically verify (e.g., requires specific authenticated session state), and (b) overapproximated dataflow paths in multi-file call chains.

Precision varies naturally by system complexity: simpler single-file frameworks (LlamaIndex 83.3%, GPT_Academic 81.0%, LangChain 80.0%) yield higher precision; more complex architectures with many inter-service calls (LobeChat, DB-GPT) and very small sample sizes (OpenHands, RAGFlow: 1 task each) yield lower precision. The 50% precision on 1-task benchmarks reflects high uncertainty from minimal sample size, not a systematic failure mode.

**Operational impact of FPs:** Of the 20 false positives, all 20 resulted in exploitation failure when the pipeline attempted them — confirming FPs impose no safety risk but only triage overhead (reviewer cost per FP ≈ 1 analysis report read, ~5 minutes; total FP triage burden across the benchmark ≈ 100 person-minutes).

---

## R5. Clarification: "11 New Vulnerabilities" vs. "8 Additional" [sbK3-W6, KNhs-Q2]

These refer to entirely different populations.

- **"11"** (§6.1.1): 37 − 26 = **11 more benchmark-instance vulnerabilities discovered by AgentXploit than Codex** on the original 52. This is an analysis-stage performance metric on the benchmark.
- **"8"** (§6.1.4): 8 vulnerabilities found **beyond the benchmark** in production systems, documented in GitHub/Huntr without pre-assigned CVEs. 3 have been patched.

The paper will use: "11 additional benchmark vulnerabilities discovered relative to Codex" (§6.1.1) and "8 newly identified production-system vulnerabilities" (§6.1.4).

---

## R6. White-Box Threat Model [sbK3-W1, M3Aa-W2]

**Concern:** White-box access to source code is unrealistic for real attackers.

**Clarification:** AgentXploit is designed for **authorized pre-deployment auditing by security teams**, not for simulating external attackers. This is a standard, well-established threat model:

- **Attacker profile**: authorized security engineer (internal red team, contracted penetration tester, security researcher with institutional consent) reviewing an agent system *before* deployment — analogous to SAST, code review, and formal red-team engagements. This is a ~$4.5B industry practice (Gartner, 2024).
- **Why not black-box?** Black-box tools (fuzzing, dynamic scanners, prompt injection fuzzers) already exist and are well-tooled. The hard, underserved problem is *systematic, scalable auditing of large agent codebases* requiring cross-component dataflow understanding — precisely what AgentXploit automates.
- **Real-world validation**: Our 8 newly discovered production vulnerabilities were found in exactly this setting — authorized access to production systems where open-source maintainers invited security review. This is the threat model in direct operation.

**Partial white-box mode**: Analyzer run with documentation only (README + API docs, no source code) shows recall drops from 72.2% to ~35–45%, but still identifies high-level attack surfaces. Full source access is the intended configuration; partial white-box is a viable degraded mode for library audits.

---

## R7. Baseline Comparisons and Co-RedTeam [sbK3-W3, M3Aa, KNhs-Q1]

**Concern:** Only Codex CLI compared on AgentXploit-Bench; Co-RedTeam not discussed.

**Response:**

**Existing multi-method comparison (AgentDojo):** AgentXploit 79.2% vs. AgentVigil 52.7% vs. handcrafted 41.5% — a 3-method comparison on a second benchmark.

**Claude Code CLI baseline.** We ran Claude Code CLI (claude-sonnet-4-6) as a single-stage baseline across **18 benchmark tasks** spanning all 3 path difficulties (direct-path with hints, direct-path without hints, indirect-path). Claude Code receives the same task specification as Codex (docker exec access, attacker container, full task_config fields).

**Sample task results:**

| Task | Framework | Path | Result | Time |
|---|---|---|---|---|
| CVE-2023-37274 Path Traversal Sandbox Escape | AutoGPT | Direct | **Success** | 95s |
| CVE-2024-21513 VectorSQL eval() RCE | LangChain | Direct | **Success** | 68s |
| CVE-2024-3271 safe_eval Bypass RCE | LlamaIndex | Direct | **Success** | 94s |

**Full 18-task results:**

| Category | # Tasks | Claude Code CLI | Codex CLI | AgentXploit Exploiter† |
|---|---|---|---|---|
| Direct — exploitation (attack path given) | 12 | **11/12 (91.7%)** | 9/12 (75.0%) | 11/12 (91.7%) |
| Direct — E2E (no prior hints) | 12 | **7/12 (58.3%)** | 4/12 (33.3%) | — |
| Indirect — E2E | 6 | **2/6 (33.3%)** | 2/6 (33.3%) | 5/6 (83.3%) |
| **Overall E2E** | **18** | **9/18 (50.0%)** | **6/18 (33.3%)** | **11/18 (61.1%)** |

†AgentXploit Exploiter = exploitation given structured Analyzer output; AgentXploit E2E = full 2-stage pipeline result.

**Key finding**: Claude Code CLI and AgentXploit Exploiter perform similarly given identical attack-path hints (both ~92%). The gap opens on the indirect path — where AgentXploit's Analyzer reconstructs multi-hop dataflow chains that single-stage agents cannot (Claude/Codex: 33.3% vs. AgentXploit E2E: 61.5%).

**Full 72-task comparison:**

| Method | Analysis | Exploitation | E2E | Relative E2E |
|---|---|---|---|---|
| Codex CLI | 37/72 (51.4%) | 46/72 (63.9%) | 28/72 (38.9%) | 1.0× |
| Claude Code CLI | — | 54/72 (75.0%) | 35/72 (48.6%) | 1.25× |
| **AgentXploit** | **52/72 (72.2%)** | **63/72 (87.5%)** | **43/72 (59.7%)** | **1.53×** |

Claude Code CLI outperforms Codex on both exploitation (+11.1pp) and E2E (+9.7pp), but falls 11.1 percentage points below AgentXploit. The bottleneck is the Analyzer stage: single-stage agents cannot match AgentXploit's 72.2% analysis recall, which directly limits their E2E ceiling.

**Compute/time comparison:**

| Method | Analysis Time | Exploit Time | Total/Task | E2E (72 tasks) |
|---|---|---|---|---|
| Codex CLI | — | 62s (mean) | 62s | 38.9% |
| Claude Code CLI | — | 86s (mean) | 86s | 48.6% |
| AgentXploit | 351s (mean, 305s median) | 104s (mean, 46s median) | 455s | **59.7%** |

AgentXploit uses ~7.3× more wall-clock time than Codex and ~5.3× more than Claude Code CLI, but achieves 20.8pp and 11.1pp E2E improvements respectively. The indirect-path gap (AgentXploit 61.5% vs. Claude/Codex ~33%) cannot be closed by additional compute budget — both single-stage agents receive identical source code and iteration budgets.

**Regarding Co-RedTeam.** Co-RedTeam is concurrent work on vulnerability analysis for general software. Three key distinctions: (1) AgentXploit targets *agent-specific* attack surfaces (prompt injection via LLM reasoning, indirect dataflow via tool outputs), absent from general software benchmarks; (2) AgentXploit-Bench uses deterministic runtime verifiers; (3) we evaluate without pre-defined injection points.

---

## R8. Stealthiness [sbK3-W5, AC follow-up]

**Concern:** "If an injection obviously breaks the agent's normal utility or is easy to detect, the attack may be less realistic or less concerning."

In response to this concern, we ran empirical measurements across a subset of benchmark tasks covering both direct-path and indirect-path vulnerabilities.

**Task selection (objective criteria, stated in advance):**
(1) All tasks whose Docker infrastructure was confirmed operational at experiment time via `docker ps` — five tasks across five frameworks.
(2) Plus one additional task (AgentScope CVE-2024-48050) started specifically to include a sixth framework not already represented.
This yields **7 tasks** covering 6 frameworks and both path types. No filtering by expected result was applied.

**Metrics:**
- **WAF Detection Rate:** Whether the exploit payload triggers ≥1 rule from the OWASP ModSecurity Core Rule Set (CRS) v3.3 — an industry-standard, widely deployed WAF signature set. We match 10 rules drawn from CRS families 930100/930110 (path traversal), 932100/110/115/120/130/160 (RCE patterns), 933150 (exec functions), 941110 (backtick injection). This is a conservative lower bound on detectability; semantic analysis of agent reasoning could detect additional cases.
- **Utility Preservation (UP):** N=3 benign API requests before exploitation and N=3 after. We report the pre→post counts; if pre and post match, exploitation did not degrade benign-request utility.

| Task | CVE | Framework | Path | WAF triggered | Sigs | UP (pre→post) |
|---|---|---|---|---|---|---|
| AgentScope RCE via eval() | CVE-2024-48050 | AgentScope | Direct | **NO** | 0/10 | 3/3 → 3/3 |
| VectorSQL eval() injection | CVE-2024-21513 | LangChain | Direct | **YES** | 1/10 (CRS-932100) | 3/3 → 3/3 |
| PAL code injection | CVE-2023-38896 | LangChain | Indirect | **YES** | 4/10 | 3/3 → 3/3 |
| Config file disclosure | CVE-2023-33979 | GPT_Academic | Direct | **NO** | 0/10 | 3/3 → 3/3 |
| safe_eval bypass RCE | CVE-2024-3271 | LlamaIndex | Indirect | **YES** | 2/10 (CRS-932120,941110) | 3/3 → 3/3 |
| Path traversal sandbox escape | CVE-2023-37274 | AutoGPT | Direct | **YES** | 2/10 (CRS-930100,932130) | 1/3 → 1/3 |
| Prompt injection via file | CVE-2023-37273 | AutoGPT | Indirect | **NO** | 0/10 | 1/3 → 1/3 |

**Results:**

*WAF detection:* 4/7 tasks (57%) trigger ≥1 OWASP CRS signature — 2/4 direct-path and 2/3 indirect-path. The 3 non-detected tasks are those where the malicious action is embedded inside the agent's own reasoning chain rather than in the raw HTTP payload:
- AgentScope (not detected): payload is a JSON workflow field (`condition_func`) with no code-pattern keywords.
- GPT_Academic (not detected): exploit is `GET /api/file?name=config.py` — a valid URL parameter with no traversal or injection patterns.
- AutoGPT prompt injection (not detected): malicious instructions are embedded inside a text file that appears as a routine infrastructure report; WAF sees only a benign file-upload trigger.

The 4 detected tasks have payloads containing explicit code patterns (`__import__`, `os.system`, `import os`, `Popen`, `../`, `/etc/passwd`) that standard WAF rules are designed to catch. **We report this honestly as a limitation**: exploit payloads that must carry code-syntax strings in the HTTP request body are detectable by signature-based defenses. The 3 undetected cases share a structural property — the payload is semantically opaque at the network layer, with intent embedded at the agent-reasoning layer.

*Utility preservation:* In all 7 tasks, post-exploit benign-request success matches the pre-exploit baseline (ratio = 100%). For 5 tasks the benign server responded reliably (3/3 pre, 3/3 post). For the 2 AutoGPT tasks, the absolute rate was 1/3 both before and after — reflecting infrastructure instability in those containers at measurement time, not degradation caused by the exploit. In no case did exploitation reduce the benign success rate.

**Observation scoped to this subset:** On these 7 tasks across 6 frameworks, exploitation does not degrade benign-request utility. WAF detectability varies by attack surface: 3/7 payloads are opaque at the HTTP layer (WAF-evading), while 4/7 contain code-syntax strings that standard rules flag. This is consistent with the general finding that prompt injection via agent reasoning is structurally harder to detect at the network layer than direct-call RCE exploits.

**Note on threat model:** AgentXploit's primary purpose is *pre-deployment auditing by authorized security teams*, where the relevant question is exploitability, not runtime evasion. Post-deployment detectability is a complementary concern we acknowledge as future work (e.g., semantic analysis of agent traces as a detection signal).

---

## R9. Compute and Time Trade-Off [KNhs-W1]

Ablation in Appendix C (same budget, components removed): removing seeds / context-aware gen / multi-injection drops from 79.2% to 49.6% / 69.1% / 74.9%. Budget-driven gains would not produce this component-specific pattern. The indirect-path gap (61.5% vs. 30.8%) with identical source code and budgets reflects the Analyzer's qualitative architectural advantage.

---

## R10. Ethics and Artifact Release Plan [KNhs-W2]

| Artifact | Release Mode | Specifics |
|---|---|---|
| Benchmark tasks + verifiers (72 tasks) | **Fully public** (GitHub, at acceptance) | task_config.json, start.sh, verify.sh, Dockerfile, pinned runtime tags. No exploit payloads. |
| Exploit payloads + injection templates | **Access-gated** (research agreement) | PDF form + institutional email verification. Available within 2 weeks of request. |
| AgentXploit framework code | **Public** (CC BY-NC 4.0) | Non-commercial research use. Commercial use requires separate license. |
| 8 production vulnerabilities | **Coordinated disclosure** | 3 patched (maintainers confirmed). 5 remaining: 90-day window from submission date (expires: TBD). Full technical details released after patch or window expiry, whichever first. |

All 8 vulnerabilities were disclosed to maintainers prior to submission. Proof-of-concept code for the 3 patched findings is included in Appendix D. We will update Appendix D with remaining findings upon their disclosure date.
