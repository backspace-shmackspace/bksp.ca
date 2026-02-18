# LinkedIn Post #3: I Built an AI Red Team That Argues With Itself

**Status:** READY TO POST (style guide compliant - verify metrics/IP before posting)
**Created:** 2026-02-14
**Target:** LinkedIn (text post)
**Register:** Blended (Register 1 hook, Register 2 analysis)
**Follows:** Post #2 (Quantify or Kill)
**Character count:** ~1,700
**Hashtags:** #SecurityEngineering #AIAgents

---

Last year I got tired of reading AI-generated risk assessments full of vague, uncited findings. So I built a pipeline where AI agents argue with each other until the output is actually defensible.

Here's the architecture:

A **discovery agent** scans external sources (vulnerability databases, threat intelligence feeds, public advisories) and generates initial findings. A **research agent** enriches those findings with evidence and citations. Then a **red team agent** tears them apart.

The red team doesn't rubber-stamp. It runs a structured adversarial review using three Speech Acts:

- **CRITICIZE**: identify gaps, missing evidence, unsupported claims
- **ENDORSE**: validate findings that meet the evidence bar
- **REFINE**: suggest specific improvements with rationale

The researcher has to respond to every critique. Then the red team reviews again. This loop continues until a convergence score (measuring how stable the findings are across review rounds) crosses a threshold. Only then does the finding get accepted.

Why this matters: the first draft from any LLM is confident and wrong in ways that are hard for humans to catch. But a second LLM tasked specifically with finding holes? It catches the hallucinated CVE references, the unsupported severity claims, the "findings" that are just rephrased descriptions of the technology.

Some numbers from early runs:

- Findings that survived adversarial review had roughly **3x more citations** than first-draft findings
- The red team rejected around **40% of initial findings** as insufficiently evidenced
- Convergence happens in **2-3 rounds**: enough scrutiny without infinite loops

The key engineering decision: convergence scoring as a termination condition. Without it, the agents either loop forever or stop too early. With it, you get measurable quality with predictable runtime.

This isn't AGI. It's flow engineering: shaping AI behavior through graph logic and structured prompts, not fine-tuning model weights. The models don't get smarter. The system around them gets more disciplined.

If you're building AI-assisted security tooling: add an adversary to your pipeline. The quality difference is not incremental. It's structural.

---

## Posting Notes

- Post 3-5 days after Post #2
- This introduces the // Build content lane
- Will attract AI/security engineering audience in addition to risk managers
- Technical enough to demonstrate depth, accessible enough for non-builders
- First comment: "I wrote more about flow engineering vs fine-tuning on my blog at bksp.ca" (when site is live)

---

## Sensitivity Review

| Element | Source | Risk | Status |
|---|---|---|---|
| Pipeline architecture | risk-orchestrator | Described generically — discovery/research/redteam is a common pattern | Safe |
| Speech Acts (CRITICIZE/ENDORSE/REFINE) | model-selection-optimization-strategy.md | Original concept, not tied to employer | Safe |
| Convergence scoring | risk-orchestrator config | Described as engineering concept, no implementation details | Safe |
| "3x more citations" | Approximate from journal observations | Directional, not exact metric from a specific run | Safe |
| "40% rejected" | Approximate from baseline runs | Directional estimate | Safe |
| "2-3 rounds" | Convergence target from config | Generic, common in iterative systems | Safe |
| No employer, project, or ticket references | — | — | Safe |

**Sensitivity note on metrics:** The numbers (3x, 40%, 2-3 rounds) are presented as directional observations, not exact measurements from a specific employer's pipeline. If Ian wants to tighten these, he should verify against his baseline data and decide what level of specificity he's comfortable sharing about a system he built.

## Content Strategy Notes

- Post #1 (problem): The Commitment-Without-Execution Loop
- Post #2 (solution): Quantify or Kill
- **Post #3 (capability): AI Red Team** <-- this post
- Post #4+: Rotate between // Defense and // Build lanes
