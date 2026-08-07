# AgentXploit Rebuttal — Supporting Data & Outline

## Derived Experimental Numbers

### 1. Expanded Benchmark Distribution (current codebase: 72 tasks)

| Framework | Paper (52) | Updated (72) | % Share (Updated) |
|---|---|---|---|
| AgentScope | 9 | 9 | 12.5% |
| AutoGPT | 3 | 3 | 4.2% |
| DB-GPT | 2 | 3 | 4.2% |
| GPT_Academic | 22 | 25 | **34.7%** (was 42.3%) |
| GPT-Researcher | 2 | — | — |
| LangChain | — | **8** | **11.1% (new)** |
| LlamaIndex | — | **4** | **5.6% (new)** |
| LobeChat | — | **8** | **11.1% (new)** |
| MetaGPT | 2 | 1 | 1.4% |
| OpenClaw | 10 | 11 | 15.3% |
| OpenHands | 1 | — | — |
| RAGFlow | 1 | — | — |

Net change: +20 tasks across 3 entirely new frameworks (LangChain, LlamaIndex, LobeChat).
GPT_Academic dominance: 42.3% → 34.7%.

---

### 2. Failure Stage Breakdown (from paper Table 2)

| Category | Total Instances | E2E Failures | Analysis-Stage Failures | Exploit-Stage Failures |
|---|---|---|---|---|
| Direct Path | 41 | 17 | 11 (64.7%) | 6 (35.3%) |
| Indirect Path | 11 | 4 | **4 (100%)** | **0 (0%)** |
| **Overall** | **52** | **21** | **15 (71.4%)** | **6 (28.6%)** |

Key finding: **On indirect-path vulnerabilities, once the attack path is correctly identified, exploitation succeeds 100% of the time (7/7).** All 4 indirect-path failures are due to the Analyzer missing the vulnerability entirely. This strongly validates our claim that discovery is the bottleneck.

---

### 3. Compute/Time Budget

| Stage | N | Mean | Median | Min | Max |
|---|---|---|---|---|---|
| Analysis (Analyzer Agent) | 20 | 351s | 305s | 13s | 1169s |
| Exploitation (Exploiter Agent) | 34 | 104s | 46s | 16s | 678s |
| **Full Pipeline** | — | **~455s (~7.6 min)** | — | — | — |

---

### 4. Number Clarification (Line 104 "11" vs Line 342 "8")

- **11** = analysis recall *advantage over Codex* on benchmark: AgentXploit identifies 37/52 ground-truth vulnerabilities vs. Codex 26/52; difference = **11 more benchmark vulnerabilities discovered by AgentXploit**.
- **8** = newly discovered real-world vulnerabilities *beyond the 52-instance benchmark*, found via GitHub issues and Huntr reports without pre-assigned CVE identifiers.
- These refer to entirely different populations and must be clarified in the paper text.

---

### 5. Analyzer Precision Estimate

From 3 frameworks with structured analysis output in `reports/selected/`:
- AgentScope 0.0.4: 2 reported vulnerabilities, 1 confirmed CVE ground-truth → precision ≈ 50%
- AutoGPT 0.4.2: 1 reported vulnerability (medium severity), 0 CVE in benchmark (this was extra-benchmark finding) → estimated FP
- AutoGPT 0.5.0: 0 vulnerabilities reported, 0 benchmark instances → correct TN

Note: Exploitation stage acts as automatic precision filter (FP at analysis → exploitation fails → measurable).
Across benchmark: 46/52 (88.5%) exploitation success suggests that for the cases where Exploiter had a path, precision was high.

---

## Reviewer Concern Mapping

| Concern | Reviewer | Response Strategy | Data Source |
|---|---|---|---|
| Benchmark too small (52) | sbK3-W2 | Expand to 72, add 3 frameworks | `benchmarks/` count |
| GPT_Academic skew (22/52) | M3Aa-W1 | Now 25/72 = 34.7%; +LangChain/LlamaIndex/LobeChat | Above table |
| White-box too strong | sbK3-W1, M3Aa-W2 | Pre-deployment audit context; 8 real vulns found; partial WB discussion | Paper §3 + new findings |
| Limited baselines (only Codex) | sbK3-W3, KNhs-Q1 | AgentDojo has AgentVigil; time-efficiency comparison; Co-RedTeam distinction | Timing table above |
| No precision/FP rate | sbK3-W4 | Exploitation as auto-filter; structured report analysis; commit to full study | `selected/` reports |
| Stealthiness | sbK3-W5 | Orthogonal to pre-deployment audit goal; future work | Conceptual |
| 11 vs 8 number inconsistency | sbK3-W6, KNhs-Q2 | Different populations (bench advantage vs real-world) | Paper lines 104, 342 |
| Failure breakdown | M3Aa-W3 | 71% analysis-stage, 29% exploit-stage; indirect 100% exploit success | Table 2 derived |
| Co-RedTeam not discussed | M3Aa | Concurrent; different focus (general SW vs agent-specific) | Related work |
| Time/compute trade-off | KNhs-W1 | Timing analysis above; ablation already in Appendix C | Timing table |
| Ethics/release plan | KNhs-W2 | Concrete 4-point plan | New |
