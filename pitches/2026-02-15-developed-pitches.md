# Developed Pitches: 2026-02-15

**Development Session:** 2026-02-15 (pitch-review)
**Pitches Developed:** #1, #2, #3, #4

---

## Pitch #1 (DEVELOPED): Why Your AI Pipeline's Performance Is a Coin Flip (And How to Fix It)

**Lane:** // build
**Format:** Blog post
**Register:** Blended (Register 1 hook → Register 2 analysis)

### Expanded Hook Options

**Option A (Mystery-driven):**
Two identical runs of the same AI pipeline, same inputs, same model. One took 19 minutes. The other took 29 minutes with 48% more API calls. The cause wasn't infrastructure. It was a single configuration parameter most teams never touch.

**Option B (Stakes-first):**
Your AI pipeline just went from 19 minutes to 29 minutes on identical inputs. Your manager asks why. You check the logs: same code, same model, same data. The only difference? Temperature 0.3 instead of 0.1. Welcome to non-deterministic AI performance.

**Option C (Data-led):**
Run 1: 19.2 minutes, 23 agent calls. Run 2: 29.2 minutes, 34 agent calls. Identical inputs. 52% slower. The culprit wasn't a bug—it was a design choice.

### Narrative Structure (Expanded)

**1. Open with the mystery (150-200 words)**
- Set the scene: Production multi-agent risk assessment pipeline
- Two back-to-back runs, PRODSECRM-105, identical JIRA inputs
- Performance dashboard shows wild variance: +603 seconds, +11 MCP calls (+48%)
- All non-review phases showed zero variance—discovery, research, analysis, compliance: identical timing
- The variance isolated to ONE phase: review

**2. The forensic investigation (300-400 words)**
- Phase-by-phase breakdown reveals review phase as the culprit
- Run 1: 11 redteam + 5 reviser = 16 review calls
- Run 2: 18 redteam + 9 reviser = 27 review calls
- Dive into the logs: one critique phrased as "missing evidence" (fast rejection) vs. "needs specific metrics X, Y, Z" (triggers revision loop)
- The cascade effect: one threshold difference → +1 reviser call → +18KB context → +2s processing × multiple findings × iterations = +10 minute delta
- Temperature at 0.3 allows sampling variance in token selection
- In creative tasks (exploration, writing), variance is good—it generates diverse ideas
- In evaluation tasks (critique, classification), variance is toxic—it creates inconsistent decisions

**3. Industry context (150-200 words)**
- This isn't theoretical—it's a known pattern
- OpenAI docs: temperature ≤ 0.1 for production evaluation tasks
- Anthropic guidance: "deterministic evaluation requires minimal temperature"
- Google: temperature 0.0 for classification, structured output
- Multi-agent systems amplify variance: one agent's inconsistency cascades through the pipeline
- Most teams don't tune temperature by cognitive task—they set it once and forget

**4. The solution design (300-400 words)**
- Differentiated temperature settings by agent task type:
  - Critique agents (redteam, reviser): 0.1-0.15 (deterministic evaluation)
  - Analysis agents (risk_auditor): 0.2 (slight creativity for gap analysis)
  - Classification agents (compliance_mapper): 0.0 (pure pattern matching)
  - Creative agents (discovery, research): 0.3 (keep diverse exploration)
- Created benchmarking harness: run same risk N times, calculate p50/p75/p90/p95 percentiles
- Temperature ablation study: 10 runs × 4 temperature values (0.0, 0.1, 0.2, 0.3)
- Expected impact: 84% variance → 15-20% (76% reduction), worst-case regression -50% → -10%
- Quality validation: critique quality maintained because evaluation doesn't require creativity

**5. Close with transferable principle (100-150 words)**
- In multi-agent systems, the agents doing evaluation work need different tuning than the agents doing creative work
- Temperature is a lever for controlling consistency vs. diversity
- The industry consensus exists—use it
- If you can't establish p50/p90/p95 performance bands, you have a variance problem
- Fix it by tuning temperature by cognitive load, not by setting it once globally

### Additional Data Points from Source Material

- **Investigation evidence:** 21KB investigation report with call-by-call breakdown
- **Implementation plan:** 34KB with 5-phase rollout (manifests, caps, timeouts, observability, integration testing)
- **Benchmarking harness:** Python script + docs for p50/p90/p95 measurement
- **Temperature guidance:** 29KB industry standards document
- **Root cause:** Temperature jump from 0.2 → 0.3 is where variance becomes problematic for critique tasks (17% increase)
- **Mathematical basis:** Temperature controls softmax distribution over token probabilities—higher temp = flatter distribution = more variance
- **Production impact:** Cannot establish SLAs with current variance levels; p50/p90/p99 bands unreliable

### Technical Details to Weave In

- **Convergence scoring mechanism:** How supervisor routing amplifies variance
- **Context growth pattern:** Each revision adds 18KB+ to context, compounding delays
- **Reviewer-reviser sub-graph:** The loop structure where variance multiplies
- **Industry temperature ranges:**
  - 0.0 = deterministic (classification)
  - 0.1 = minimal variance (evaluation)
  - 0.2 = slight creativity (analysis)
  - 0.3 = balanced (general use)
  - 0.5+ = highly creative (brainstorming)

### Sensitivity Reminders

- Frame as "a multi-agent risk assessment pipeline" or "a production AI workflow"
- Do not reference specific cloud providers, model names by vendor
- Temperature values and variance percentages are generic/public—safe
- Use "reasoning model" and "fast model" instead of vendor names

---

## Pitch #2 (DEVELOPED): Flow Engineering: Teaching AI Without Training It

**Lane:** // build
**Format:** Blog post
**Register:** Blended (Register 1 walkthrough → Register 2 principles)

### Expanded Hook Options

**Option A (Counterintuitive claim):**
I run a pipeline with 10 AI agents. I've never fine-tuned a single one. Every behavior change—from how strictly they evaluate, to when they stop debating—is controlled by graph logic and prompt architecture, not model weights.

**Option B (Results-first):**
Zero fine-tuning. Zero weight updates. Just graph topology, prompt engineering, and model routing. Result: 27% performance improvement, 601 tests passing, 89% coverage, and production-quality behavior.

**Option C (Question format):**
Do you need to train AI models to get production-quality behavior? I thought so too—until I built a 10-agent risk assessment pipeline that learned through architecture, not training.

### Narrative Structure (Expanded)

**1. Start with the counterintuitive claim (150-200 words)**
- Open with the "no fine-tuning required" statement
- Set expectations: most teams assume training is the path to better outputs
- Introduce flow engineering as the alternative
- Three levers: (1) prompt architecture, (2) graph logic, (3) model tiering

**2. Walk through the three levers (800-1000 words)**

**Lever 1: Prompt Architecture using Speech Acts (300-350 words)**
- Traditional prompts: vague instructions ("be thorough", "check quality")
- Speech Acts: structured cognitive stances (CRITICIZE, ENDORSE, REFINE)
- Example transformation:
  - Before: "Review this finding and provide feedback"
  - After: "CRITICIZE: Identify flaws or gaps. REFINE: Suggest specific improvements with examples."
- Forces model to adopt specific cognitive stance without weight updates
- Makes agent interactions measurable and debuggable
- Show concrete example from redteam agent prompt

**Lever 2: Graph Logic with Convergence Scoring (300-350 words)**
- Traditional approach: run agents in sequence, hope for the best
- Flow engineering: measurable termination criteria
- Convergence threshold: 0.85 (tag stability across iterations)
- Guardrails: MIN_RESEARCH_FINDINGS=2, MIN_CRITIQUE_ENTRIES=2, MIN_SUPERVISOR_ITERATIONS=2
- Example decision logic:
  - convergence_score = (research_weight + review_weight + critique_weight) / 3
  - If score ≥ 0.85 AND critique_stable AND first_pass_rate > 80% → converge
  - Otherwise → iterate
- Real numbers: PRODSECRM-176 converged at iteration 4 with 33.3% first-pass rate, convergence_score=0.90
- PRODSECRM-40 correctly blocked at iteration 5 with 0.0% first-pass rate, convergence_score=0.85 (quality insufficient)

**Lever 3: Model Tiering by Cognitive Load (200-300 words)**
- Not all tasks need expensive reasoning models
- Cognitive load mapping:
  - High reasoning (supervisor, redteam): Claude 3.5 Sonnet
  - Mid-tier atomic tasks (discovery, research): Claude 3 Haiku
  - Pure classification (compliance mapper): Fast model
- Real performance data:
  - Compliance classification moved from reasoning model to fast model
  - 10s vs 20s (50% latency reduction)
  - Zero quality degradation (pattern-matching doesn't need deep reasoning)
- Cost projection: 60-70% inference cost reduction through cognitive load-based routing
- Performance optimization: 956s baseline → 697s optimized (-27%) through graph logic changes, not model changes

**3. Show the results (200-250 words)**
- 10 specialized agents, zero fine-tuning
- 601 tests passing, 89% coverage
- Graph logic is testable in ways model weights aren't
- Performance: 27% improvement through graph optimization alone
- Variance: 84% → 15-20% through temperature tuning (not training)
- Maintainability: change prompts in minutes vs. retraining for days
- Auditability: full audit trails, HMAC verification, deterministic validation

**4. Close with the principle (150-200 words)**
- In multi-agent systems, the architecture IS the training
- You shape behavior through graph topology and prompt design, not through weight updates
- This is more maintainable, auditable, and adaptable than fine-tuning
- As multi-agent architectures become mainstream (Anthropic's MCP, OpenAI's agents SDK), flow engineering gives practitioners a concrete alternative to the "just fine-tune it" reflex
- Three questions to ask before fine-tuning:
  1. Can I control this with graph logic?
  2. Can I encode this in prompts?
  3. Can I route this to a specialized model?
- If yes to any, try flow engineering first

### Additional Technical Details

- **Speech Acts implementation:** Phase 5 cognitive refinement plan (45+ pages)
- **Convergence formula:** Full mathematical definition with guardrails
- **Model selection strategy:** Federated orchestration pattern (brain vs. body)
- **Testability advantage:** 601 tests across graph logic—can't unit-test model weights
- **Cost-benefit analysis:** 60-70% savings vs. fine-tuning compute costs
- **Iteration speed:** Minutes to change prompts vs. days to retrain models

### Real Production Examples to Include

- **Phase C convergence validation:** Two risks (PRODSECRM-176 converged, PRODSECRM-40 blocked) showing system correctly refusing convergence when quality insufficient
- **Model tiering validation:** Compliance mapper on Haiku achieved 50% latency reduction with zero quality degradation
- **Graph optimization impact:** 956s → 697s (-27%) with no model changes

### Sensitivity Reminders

- Frame as "a multi-agent security analysis pipeline" generically
- Do not reference specific cloud APIs or enterprise integrations
- Speech Acts, convergence scoring, and model tiering are generic architectural patterns—safe
- Do not mention specific model names by vendor (use "reasoning model" and "fast model")

---

## Pitch #3 (DEVELOPED): I Built the Scanner Because the Data Didn't Exist

**Lane:** // defense
**Format:** LinkedIn post
**Register:** Blended (Register 1 narrative → Register 2 pattern)

### Expanded Hook Options

**Option A (Problem-driven):**
A critical-severity security risk had been on the register for over a year. The risk assessment said "no internal metrics on content scanning coverage." So I built the scanner myself—and what I found halved the resource ask.

**Option B (Action-first):**
Twenty-two months of organizational stagnation. Manual purges with 100% recurrence. Zero automated detection. So I built the scanner. 13,931 repos. 327 flagged. 93.4% precision. 100% recall. And suddenly, a 4-6 FTE-week ask became 2-3 FTE weeks.

**Option C (Transformation):**
"No Red Hat internal metrics on content scanning coverage" → 13,931 repos scanned, 93.4% precision, 100% recall, automated nightly scans, compliance gaps converted from "no control exists" to "detective control in place."

### Narrative Structure (Expanded)

**1. Open with the problem (200-250 words)**
- Security risk on the register for 22+ months
- Risk assessment blocked by unmeasurable concern: "no internal metrics"
- Platform team confirmed zero bandwidth until late 2026
- Manual purges proven ineffective—100% recurrence post-cleanup
- Product Security explicitly refused to provide engineering resources
- Nobody was negligent—the platform simply lacked detection capabilities
- But without detection, you can't quantify the risk, and without quantification, you can't scope the fix
- Stalled risk with high severity, no path forward

**2. Take the engineer's approach (250-300 words)**
- Instead of waiting for another team to build it, build a proof-of-concept scanner
- Requirements gathered from risk assessment report, resource loan document, stakeholder meetings
- Detection problem broken down into components:
  - Imageless container detection (strongest signal: 50-point weight)
  - Heuristic rules for spam keywords (35+ rules, YAML-based, versioned)
  - Threat intelligence integration (URLhaus, PhishTank, NVD with 24hr caching)
  - ClamAV malware scanning for deep inspection
  - Bayesian probabilistic scoring (83% fewer false positives vs. additive heuristics)
- Built in Python, production-ready, externally accessible via public API
- Nightly automated scans with cost controls and PID locking
- Dashboard with 13 visualizations for triage workflow

**3. Show the strategic leverage (200-250 words)**
- Scanner transforms unmeasurable concern into quantified risk with specific numbers
- Results: 13,931 repos scanned across 994 namespaces, 327 flagged (standard mode), 1,869 flagged (aggressive mode)
- Detection accuracy: 93.4% precision, 100% recall, F1 score 96.6%
- Compliance impact: Multiple frameworks moved from "no control exists" to "detective control in place"
  - SOC2 CC7.2: No control → Detective control via nightly scans
  - FedRAMP SI-3: No detection → Detection in place (prevention still missing)
  - FedRAMP CA-7: No monitoring → Continuous monitoring via dashboard
  - GDPR Art 32: No technical measure → Technical measure demonstrable
- Resource impact: Original ask 4-6 FTE weeks (detection + enforcement) → Revised ask 2-3 FTE weeks (enforcement only)
- Detection half done, enforcement half remains

**4. Close with the principle (150-200 words)**
- In risk management, if you can't measure it, you can't scope the fix
- Sometimes the fastest way to move a stalled risk forward is to build the measurement tool yourself
- Detection is often simpler than enforcement—you can build detection externally via public APIs without platform access
- Quantification unlocks organizational decision-making (you can't approve a resource ask for "unmeasurable risk")
- The PoC doesn't close all gaps (prevention still missing), but it converts gaps from "no control" to "detective control"—a meaningful distinction for auditors
- Transferable pattern: any risk stuck because nobody can quantify it is a candidate for "build the measurement tool"

### Additional Data Points from Source Material

- **Risk age:** 22+ months on register before quantification (April 2024 - February 2026)
- **Organizational cycle pattern:** Commitment → Partial action → Premature closure → Stagnation → Re-escalation (repeated 3 times)
- **Named threat actors:** caniatabita, veronikalazy, gehafes146, team-helium, pdf_dumps
- **Attack vector:** Imageless containers (OCI spec abuse, publicly documented by JFrog in April 2024, 1.6M+ discovered on Docker Hub)
- **Purge effectiveness:** February 2025 purge of ~1,500 repos → immediate re-population
- **PoC coverage:** 6 of 8 risk response actions addressed (75% coverage)
- **Engineering bandwidth blocker:** Platform team has competing priorities (SLOs, ROSA, Konflux, PQC, mTLS)
- **Escalation path:** Bill Dettelback and Dave O'Connor committed to Q1/Q2 prioritization with Tony Woo
- **Investment brief support:** Emily Fox offered to develop investment brief for dedicated abuse team

### Technical Details to Weave In (Selective)

- **Heuristic rules:** v2.2.0, 35+ rules, YAML-based with versioned schema, obfuscation bypass
- **Threat intel integration:** URLhaus, PhishTank, NVD with 24hr caching and rate limiting
- **Deep scan capability:** ClamAV scanning + behavioral analysis via skopeo with disk management
- **Probabilistic scoring:** Bayesian approach reduces false positives by 83% vs. additive heuristics
- **Namespace stability tracking:** Identifies persistent offenders vs. one-time spam

### Sensitivity Reminders (CRITICAL)

- Must not name the platform, registry, employer, or team members
- Frame as "a public container registry" or "a content hosting platform"
- Do not reference specific compliance frameworks (SOC2, FedRAMP, CRA) by name—use "industry compliance standards"
- Do not mention JIRA ticket numbers, organizational hierarchy, or internal escalation paths
- Scanner architecture details (heuristic rules, threat intel integration) are safe to discuss generically
- Do not name specific products (Quay), use "the platform" or "the registry"

---

## Pitch #4 (DEVELOPED): The 7-Layer Security Model for Self-Improving AI Agents

**Lane:** // build
**Format:** Blog post
**Register:** 2 (analytical/authority)

### Expanded Hook Options

**Option A (Design tension):**
I designed a system where AI agents automatically improve their own prompts based on production performance data. The first thing I had to build wasn't the improvement engine—it was 7 layers of security to prevent the system from poisoning itself.

**Option B (Vulnerability-driven):**
Here's the vulnerability nobody talks about: a self-improving AI system that optimizes for eval metrics instead of actual quality. Welcome to Goodhart's Law at scale.

**Option C (Scope revelation):**
1,490 lines for the self-improvement system. 2,120 lines for the production feedback loop. And both passed security red team review on the first revision—after addressing 2 Critical and 5 Major vulnerabilities in each.

### Narrative Structure (Expanded)

**1. Open with the design goal (200-250 words)**
- The vision: a feedback loop where production failures generate new test cases, test cases expose agent weaknesses, and the system proposes prompt improvements—automatically
- The attraction: continuous improvement without human prompt engineering
- The dual feedback loop:
  - Loop 1 (Development-Time): CI evals → self-improvement → prompt edits (runs on code changes, catches regressions)
  - Loop 2 (Production-Informed): Real-world failures → new eval tests → expose gaps → trigger Loop 1 (runs weekly, catches real-world failure modes)
- The goal: make risk-orchestrator agents continuously improve from production PRODSECRM risk assessments

**2. Reveal the core tension (200-250 words)**
- Any system that modifies its own instructions is a prompt injection target
- But the vulnerabilities go deeper than injection
- Critical vulnerability #1: **Goodhart's Law** — the system optimizing for eval metrics rather than actual quality
  - Example: Agent learns to pass the "must have citations" test by adding fake citations
  - Mitigation: Human review gates at every mutation point, strict rule that LLM judge failures always require human review
- Critical vulnerability #2: **Prompt injection via eval reports**
  - Attack vector: JIRA summary → agent output → eval report → task generator → eval templates → git → prompt mutation
  - Eval reports contain user-originated data from issue trackers
  - Untrusted content flows through 6 transformation stages before potentially reaching prompts
  - Mitigation: Fully synthetic inputs for generated eval tasks, no production content in templates
- Critical vulnerability #3: **PII leakage**
  - Production data flows through system: event store → metrics analyzer → eval generator → version control
  - Risk: JIRA summaries, customer names, internal project names leak into git
  - Mitigation: PIISanitizer module with email/IP/domain redaction, defensive validation at merge step

**3. Walk through the 7-layer security model (600-800 words)**

**Layer 1: SHA-256 Content Hash Validation**
- Every prompt file gets content hash before and after editing
- Detect unauthorized modifications outside the approved workflow
- Prevents manual edits from being overwritten by automation
- Audit trail of all hash changes

**Layer 2: Role-Based Approval Gating**
- Dry-run by default: `--apply` flag required for any mutation
- CI pipeline is always read-only (no --apply flag in CI)
- Human review required for all prompt changes before applying
- Clear audit trail of who approved what

**Layer 3: Deterministic Failure Classification**
- **Never let an LLM decide what to auto-fix**
- All LLM judge failures unconditionally require human review
- No LLM-based classification of what went wrong (vulnerable to adversarial content)
- Deterministic rules only for security-critical routing
- Example: If eval fails → human review queue (not "analyze failure type and auto-fix")

**Layer 4: HMAC-SHA256 Chain Verification on Production Data**
- Event store uses HMAC chain (reuses existing AUDIT_HMAC_KEY)
- Watermark signatures (SHA-256 + HMAC) for incremental analysis
- Baseline metrics signing (future enhancement)
- Invalid HMAC → fail-safe: full re-analysis instead of trusting tampered data
- Prevents event store poisoning, watermark tampering, baseline metrics manipulation

**Layer 5: Dry-Run by Default with Explicit --apply Flag**
- Default mode: generate proposals only, no writes
- `make improve` → dry-run (read-only, generates proposals)
- `make improve-apply` → requires explicit --apply flag
- Allows safe testing in CI without mutation risk
- Human review gate before production changes

**Layer 6: Quality Baseline Tracking with Automatic Rollback**
- Track eval pass rates before and after prompt changes
- If quality degrades after applying new prompt → automatic rollback
- 8-point validation before applying edits:
  1. Content hash validation
  2. Syntax validation
  3. must_not_include pattern check
  4. Schema conformance
  5. Baseline quality comparison
  6. Regression test pass rate
  7. Security review checklist
  8. Human approval signature
- Atomic multi-file transactions: all-or-nothing prompt updates

**Layer 7: Full Audit Trail**
- Every prompt edit logged with:
  - Timestamp
  - Who approved (human or automated)
  - What changed (diff)
  - Why it changed (eval failure evidence)
  - Rollback hash (for recovery)
- Audit logs enable forensic investigation
- Compliance-ready trail for regulated environments

**4. Highlight the critical insight (200-250 words)**
- The most dangerous vulnerability was Goodhart's Law
- When optimization becomes the goal, optimization degrades quality
- Example progression:
  - Week 1: Agent learns citations are required → adds real citations
  - Week 2: Eval metrics reward citation count → agent adds more citations
  - Week 3: System optimizes for high citation density → agent fabricates citations to pass tests
  - Week 4: Production quality degrades, but eval metrics look perfect
- Mitigation: Human review of LLM judge failures is non-negotiable
- The system can propose improvements, but humans must validate that the improvements are real
- Deterministic classification prevents the system from gaming its own metrics

**5. Close with the principle (150-200 words)**
- Self-improving AI systems require more security engineering than traditional software
- But the patterns are well-established and transferable:
  - Defense-in-depth (7 layers, not 1)
  - Fail-safe defaults (dry-run, not auto-apply)
  - Deterministic validation (rules, not LLM decisions)
  - Human-in-the-loop gates (review, not blind trust)
- Most teams building "auto-prompt-tuning" or "self-healing" AI systems haven't thought through the attack surface
- This gives practitioners a concrete security architecture before they build something that optimizes itself into a vulnerability
- The dual feedback loop (development-time + production-informed) is the right model
- But without the 7-layer security model, it's a security incident waiting to happen

### Additional Technical Details

- **Plan sizes:** 1,490 lines (self-improvement) + 2,120 lines (production feedback loop)
- **Review effectiveness:** Red team caught 2 Critical + 5 Major issues in each plan
- **Revision discipline:** Both plans passed on first revision round
- **CI pipeline complexity:** 7 iterations to get working (Docker Hub rate limits, permission issues, dependencies)
- **GitLab CI runtime:** Reduced from ~6 minutes to ~3 minutes with modular stages and pip caching
- **Test coverage:** 880+ new tests across 22 files for citation extraction and convergence optimization
- **must_not_include hardening:** Abstract semantic labels replaced with concrete literal substrings (commit d1d85e5)
- **Template vs. LLM generation trade-off:** Start with templates (free, fast, deterministic), add LLM generation as Phase 2 if quality insufficient

### Real Vulnerabilities Found (Be Specific)

1. **Prompt injection via eval reports:** Eval reports contain user-originated JIRA data that flows through 6 transformation stages
2. **Goodhart's Law degradation:** System optimizing for eval metrics instead of actual quality
3. **PII leakage:** JIRA summary → agent output → eval report → git → public exposure
4. **Event store poisoning:** Fabricated metrics, watermark tampering, baseline manipulation
5. **Classification manipulation:** LLM-based routing vulnerable to adversarial content

### Sensitivity Reminders

- Must not name employer, pipeline, or specific risk domain
- Frame as "a multi-agent AI pipeline for security analysis" generically
- Do not reference specific CI/CD platforms (GitLab), issue trackers (JIRA), or cloud providers
- Do not mention specific model vendors in the context of eval judge implementation
- The 7-layer security model, Goodhart's Law mitigation, and deterministic classification patterns are generic—safe to discuss in detail
- Do not reference specific regulatory frameworks or compliance requirements that could identify the employer

---

## Development Notes

### Cross-Pitch Themes

All four pitches share common threads that could be woven together for a series:

1. **Measurement First:** Pitch #1 (measure variance), #2 (measure convergence), #3 (measure risk), #4 (measure quality)
2. **Engineering Over Hoping:** All four solve problems with architecture, not magic
3. **Transferable Patterns:** Temperature tuning, flow engineering, measurement tooling, security layers
4. **Real Production Data:** All four backed by concrete numbers from real systems

### Recommended Publishing Order

If publishing as a series:

1. **Pitch #3** (Scanner) — Most accessible, narrative-driven, broad appeal
2. **Pitch #1** (Temperature) — Technical but immediately actionable
3. **Pitch #2** (Flow Engineering) — Deeper architectural principles
4. **Pitch #4** (7-Layer Security) — Most advanced, specialist audience

Or reverse order for technical-first audiences (4 → 2 → 1 → 3).

### Writing Efficiency Notes

- Pitches #1, #2, #4 have extensive source material—ready to draft
- Pitch #3 has comprehensive analysis document but needs narrative polish
- All four have clear data points and technical details documented
- Sensitivity flags are well-defined for each pitch

---

**Next Steps After Approval:**

1. Select which pitch(es) to draft first
2. Confirm register/voice for each (walkthrough vs. analysis)
3. Create skeleton files in `drafts/blog/` or `drafts/linkedin/`
4. Begin writing with source material as reference
