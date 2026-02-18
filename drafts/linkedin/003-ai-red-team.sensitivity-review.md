# Sensitivity Review: LinkedIn Post #3 - I Built an AI Red Team That Argues With Itself

**Verdict:** CLEAR

This post is safe to publish. No identifiable employer, colleague, client, or project references. The content is framed as a personal AI system Ian built, not employer intellectual property.

---

## Findings

### 🟢 Noted (acceptable as-is)

**"Last year I got tired of reading AI-generated risk assessments..."**
- **Why it's OK:** "Last year" is a vague timeframe. "I built" attributes the system to Ian personally, not to Red Hat or IBM. No specific project identifier.
- **Risk level:** Low. Framed as personal project.

**Pipeline architecture (discovery → research → red team)**
- **Why it's OK:** This is a common multi-agent pattern. Ian presents it as his own design ("I built a pipeline"), not as Red Hat or IBM proprietary architecture.
- **Risk level:** None. Generic architectural pattern.

**Speech Acts (CRITICIZE, ENDORSE, REFINE)**
- **Why it's OK:** These are Ian's design choices, not employer IP. The terms are descriptive, not proprietary.
- **Risk level:** None. Personal methodology.

**Convergence scoring as termination condition**
- **Why it's OK:** This is an engineering concept, not a trade secret. Ian doesn't share implementation details (code, prompts, thresholds), just the principle.
- **Risk level:** None. Generic engineering principle.

**Metrics: "3x more citations," "40% rejected," "2-3 rounds"**
- **Why it's OK:** The draft's sensitivity review notes these are "directional observations, not exact measurements." They're presented as approximate results from early runs, not as official Red Hat or IBM product metrics.
- **Risk level:** Low. If these numbers are approximations (as stated in the draft), they're safe. If they're exact metrics from employer systems, they could be borderline. Recommend Ian verify these are directional estimates he's comfortable sharing.

**No named entities found:**
- No people names
- No company names (Red Hat, IBM not mentioned)
- No product names
- No project identifiers (no JIRA keys, repo names, internal project names)
- No internal URLs or system names

---

### 🟡 Should Verify (reduces risk)

**Metrics verification (line 31-35):**
- **What's flagged:** "3x more citations," "40% rejected," "2-3 rounds"
- **Why it matters:** If these are exact measurements from a Red Hat or IBM system, they could be considered proprietary performance data. If they're directional approximations Ian is comfortable sharing, they're safe.
- **Suggested verification:** Ian should confirm:
  1. Are these approximate/directional? (If yes, safe.)
  2. Are these from a personal side project? (If yes, safe.)
  3. Are these exact metrics from employer systems? (If yes, consider making them more approximate: "roughly 3x," "around 40%," "typically 2-3 rounds")

**Recommendation:** Change "3x more citations" to "roughly 3x more citations" and "40%" to "around 40%" to make it clear these are directional observations, not official metrics.

---

### Fingerprint Risk Assessment

**Can combinations of anonymized details identify the source?**

**Low risk.**

The post describes:
1. A personal AI pipeline ("I built")
2. An architectural pattern (discovery → research → red team)
3. Approximate performance metrics

None of these details point to a specific employer or project. The key protective framing: "Last year I got tired... So I built a pipeline." This positions the system as Ian's personal work, not Red Hat or IBM IP.

**Could Ian's LinkedIn connections recognize this?**

Possibly—if Ian has discussed this architecture internally at Red Hat or presented it at a team meeting, colleagues might recognize the pattern. But recognition of an architecture is different from identification of proprietary IP. The post doesn't say "at Red Hat we built" or "for my current employer." It's framed as "I built."

**Could this embarrass or harm Ian's employer?**

No. The post doesn't identify Red Hat, doesn't critique Red Hat's AI practices, and doesn't claim Red Hat's systems produce "vague, uncited findings." It's a critique of the state of AI-generated content generally, not of any specific employer.

**Could this violate NDA or employment agreements?**

**Borderline, requires judgment call.**

The key question: Is this Ian's personal side project, or is this Red Hat IP?

**If this is a personal side project Ian built on his own time with his own resources:**
- ✅ Safe to publish. No NDA violation.

**If this is based on or derived from Red Hat's risk-orchestrator system:**
- ⚠️ Borderline. Sharing architectural patterns without code/prompts is usually safe, but if Red Hat considers the multi-agent adversarial pattern proprietary, this could be sensitive.
- **Mitigation:** The post doesn't share implementation details (code, prompts, thresholds, infrastructure). It describes a pattern. Most employment agreements allow sharing general learnings and methodologies.

**Recommendation:** Ian should verify:
1. Is this architecture his personal design, or Red Hat's?
2. If it's derived from work done for Red Hat, has he cleared sharing this pattern with his manager?

Given that Ian's boss gave Post #1 a thumbs up, Ian likely has a good sense of what's safe to share. But this post is more technical and describes a specific system, so it's worth double-checking.

---

## Recommendation

**Publish after verification.**

This post is likely safe, but Ian should verify two things before publishing:

1. **Metrics verification:** Confirm the numbers (3x, 40%, 2-3 rounds) are directional approximations he's comfortable sharing, not exact proprietary metrics. Consider adding "roughly" or "around" to make it clear they're estimates.

2. **IP verification:** Confirm this is Ian's personal architecture/side project, not Red Hat proprietary IP. If it's based on work done for Red Hat, verify he's comfortable sharing the architectural pattern (without code/prompts).

If both checks pass, this is safe to publish. The post doesn't identify Red Hat, doesn't share implementation details, and frames the system as Ian's personal work.

---

## Notes for Ian

The draft includes a sensitivity review table (lines 54-66) that references internal documents and systems:
- "risk-orchestrator"
- "model-selection-optimization-strategy.md"
- "baseline runs"
- "Convergence target from config"

**These internal references should NOT be published.** They're fine for your personal notes, but delete that table before posting. The LinkedIn post itself (lines 11-40) is clean and contains no identifiable references.

**Action:** Delete lines 43-73 (the entire "Posting Notes" and "Sensitivity Review" sections) before posting to LinkedIn. Those are draft metadata, not content.

---

## Final Check

**Published content (lines 11-40):** ✅ LIKELY CLEAR (pending verification)
**Draft metadata (lines 43-73):** ⚠️ DELETE before posting (internal references)

**Overall verdict:** Safe to publish after:
1. Verifying metrics are directional estimates (add "roughly" / "around")
2. Verifying this is Ian's personal architecture, not Red Hat IP
3. Deleting draft metadata section
