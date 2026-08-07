Useful Agent Red-Teaming Framework with Benchmark and Threat-Model Concerns
Official Reviewby Reviewer sbK310 May 2026, 14:29 (modified: 22 May 2026, 21:58)Program Chairs, Area Chairs, Reviewers Submitted, Authors, Reviewer sbK3Revisions
Summary:
The paper proposes AgentXploit, an end-to-end red-teaming framework for AI agents. Unlike prior work that mainly assumes predefined attack paths, AgentXploit analyzes a target agent’s codebase to discover risky tools, sensitive operations, and feasible attack paths, then executes exploits in a sandbox to validate them. The paper also introduces AgentXploit-Bench, a benchmark with 52 vulnerability instances from 9 popular agent frameworks, based on CVEs and public security issues. Experiments show that AgentXploit outperforms Codex on AgentXploit-Bench and outperforms AgentVigil and handcrafted attacks on AgentDojo.

Reasons To Accept:
(1) The problem is well motivated. As LLM agents gain access to tools, files, browsers, and APIs, end-to-end security auditing becomes increasingly important. Prior red-teaming methods often assume the attack path is already known, while this paper tries to discover and validate attack paths automatically.

(2) AgentXploit-Bench is a useful contribution. It includes real-world agent frameworks and vulnerabilities derived from CVEs and public issues, with deterministic verifiers.

(3) The empirical results are promising. On AgentXploit-Bench, AgentXploit achieves 59.6% end-to-end success, compared with 38.5% for Codex. It also performs well on AgentDojo, reaching 79.2% attack success.

Reasons To Reject:
(1) There is concern about whether the threat model is practical. The white-box audit setting is useful, but less realistic for real attackers. Also, for indirect prompt injection, even if an attacker can place malicious content in an external source, the agent may not necessarily read it, which can make the attack less severe in practice.

(2) The benchmark is relatively small, with only 52 instances. This is useful as an initial benchmark, but could be limited to support broad claims about real-world agent security.

(3) The baseline comparison is limited. AgentXploit-Bench only compares against Codex CLI. More baselines, such as OpenHands, SWE-agent, or Claude Code, would make the results stronger and help validate the gain from the proposed discovery-validation design.

(4) The paper reports analysis recall but not precision or false-positive rate. The Analyzer finds 37/52 ground-truth vulnerabilities, but it is unclear how many extra reported vulnerabilities are false positives. In real auditing, triage cost is important, so precision matters as much as recall.

(5) Stealthiness is not analyzed. High attack success rate is only one aspect of attack quality. If an injection obviously breaks the agent’s normal utility or is easy to detect, the attack may be less realistic or less concerning.

(6) There is a possible inconsistency in the number of newly discovered vulnerabilities. Line 104 mentions "eleven new valid vulnerabilities upon human confirmation," while line 342 says AgentXploit identifies "8 additional vulnerabilities." This should be clarified.

Rating: 4: Ok but not good enough - rejection
Confidence: 4: The reviewer is confident but not absolutely certain that the evaluation is correct
Ethics Flag: No
Add:
This paper present AgentXploit, a two-stage white-box red-teaming framework for LLM agent systems. Given a target agent repository, an Analyzer Agent first read the codebase to discover attack paths and vulnerable dataflows, then an Exploiter Agent validate these paths through runtime exploit execution in sandboxed environment. Authors also introduce AgentXploit-Bench, a benchmark of 52 real-world vulnerability instances from 9 popular agent systems. AgentXploit achieve 59.6% end-to-end success rate compared to 38.5% for Codex baseline, and 79.2% on AgentDojo.
Official Reviewby Reviewer M3Aa10 May 2026, 10:37 (modified: 22 May 2026, 21:58)Program Chairs, Area Chairs, Reviewers Submitted, Authors, Reviewer M3AaRevisions
Summary:
Quality. Evaluation is comprehensive, covering analysis, exploitation, end-to-end success, and ablation. Benchmark construction from real CVEs is genuine strength. However, main baseline is Codex, a general-purpose coding agent and not a dedicated security tool. Co-RedTeam, a concurrent work that also decompose vulnerability analysis into coordinated discovery and exploitation stages, is not discussed or compared, which is notable gap.
Originality. Combining repository-level attack-path discovery with runtime validation for LLM agents specifically is novel. CyberGym and similar benchmarks provide cybersecurity evaluation but target general software, not AI agent systems. AgentXploit-Bench is more focused on agent-specific vulnerabilities, which is meaningful distinction. Analyzer Agent’s dynamic task queue and external memory for long-horizon codebase reasoning is interesting, though similar ideas exist in general coding agent literature.
Significance. Finding that 88.5% of identified vulnerabilities can be reliably exploited once attack paths are known suggest the real bottleneck is in discovery, not exploitation. The 8 new real-world vulnerabilities found beyond the benchmark provide concrete evidence of practical impact.
Reasons To Accept:
Attack-path discovery from source code before exploitation is novel framing not previously applied to LLM agent security specifically.
AgentXploit-Bench is genuine contribution — real CVEs, real agent frameworks, deterministic verifiers, end-to-end evaluation without pre-defined injection points.
Strong empirical gains especially on indirect-path vulnerabilities (63.6% vs. 27.3% end-to-end).
Discovery of 8 new real-world vulnerabilities demonstrate practical usefulness.
Reasons To Reject:
AgentExploit-Bench is heavily skewed : 22 of 52 instances come from single project (GPT-Academic), which raise question about benchmark diversity.

White-box assumption requires full source code access, which is quite strong and not well-justified for the stated threat model.

No analysis of where the 40% end-to-end failures happen (analysis stage, exploitation, or both).

Questions To Authors:
Why 22 of 52 benchmark instances come from GPT-Academic alone? What is plan to make benchmark more balanced?

White-box assumption require source code access. how realistic is this, and have you consider partial white-box setting?

For the 40% of failed end-to-end instances, where exactly does failure happen, analysis or exploitation stage?​​​​​​​​​​​​​​​​

Rating: 4: Ok but not good enough - rejection
Confidence: 4: The reviewer is confident but not absolutely certain that the evaluation is correct
Ethics Flag: No
Add:
review
Official Reviewby Reviewer KNhs08 May 2026, 08:10 (modified: 22 May 2026, 21:58)Program Chairs, Area Chairs, Reviewers Submitted, Authors, Reviewer KNhsRevisions
Summary:
This paper presents AgentXploit, an automated end-to-end red-teaming framework for AI agents. The key motivation is that existing red-teaming methods often assume predefined attack paths, while real-world agent systems require discovering where attacker-controlled inputs enter, how they propagate through the system, and whether they can reach sensitive operations. AgentXploit addresses this by combining a repository-level Analyzer Agent, which identifies risky tools, sensitive operations, and feasible attack paths, with an Exploiter Agent, which validates the discovered paths through runtime exploit execution in sandboxed environments. The paper also introduces AgentXploit-Bench, a benchmark of 52 vulnerability instances across 9 popular open-source agent frameworks, derived from CVEs and publicly reported security issues. Experiments on AgentXploit-Bench and AgentDojo show that AgentXploit outperforms strong baselines such as Codex and AgentVigil, especially on indirect-path vulnerabilities that require long-horizon reasoning and adaptive exploitation.

Reasons To Accept:
The paper studies an important and timely problem. The security of LLM-based agents is becoming increasingly important as agents gain access to external tools, file systems, browsers, code execution, and communication APIs. The paper correctly identifies that practical agent red-teaming requires more than optimizing adversarial prompts. It requires discovering attack surfaces and validating exploitability end to end.

The end-to-end formulation is clear and useful. The two-stage design, consisting of attack-path discovery followed by runtime exploit validation, gives the work a coherent structure. The Analyzer Agent and Exploiter Agent have clearly separated roles, and the paper makes a convincing case that both stages are necessary for realistic security evaluation of modern AI agents.

AgentXploit-Bench is a valuable contribution. The benchmark covers 52 validated vulnerability instances from 9 widely used open-source agent frameworks. The use of CVEs, public issue reports, pinned runtimes, and deterministic verifiers makes the benchmark practically meaningful. This could be useful for future research on agent security, automated vulnerability discovery, and exploit validation.

Reasons To Reject:
The paper lacks a detailed time and compute trade-off analysis. This makes it hard to assess whether AgentXploit is more effective because it reasons better, or because it spends more search and execution budget.

The security release and misuse discussion could be more concrete. The paper includes detailed exploit-oriented examples and injection templates. While these examples help understand the system, they also raise dual-use concerns. The ethics statement is useful, but the paper would benefit from a more concrete artifact release plan, such as what exploit details will be released, whether access will be gated, and how responsible disclosure was handled.

Questions To Authors:
Can the authors evaluate AgentXploit against a broader set of baselines?

Could the authors clarify the number of newly discovered vulnerabilities reported in the paper?

Rating: 6: Marginally above acceptance threshold
Confidence: 3: The reviewer is fairly confident that the evaluation is correct
Ethics Flag: No
