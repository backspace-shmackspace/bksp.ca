# How to Talk About Risk When Your VP Doesn't Care About Your Pipeline

**Status:** APPROVED — awaiting first draft
**Approved:** 2026-02-24
**Lane:** // defense
**Format:** LinkedIn post
**Register:** 2 (analytical/authority)
**Pitch source:** `pitches/2026-02-24-pitches.md`

---

## Writing Guidance

### Hook
I built a multi-agent risk assessment pipeline. Event sourcing, HMAC integrity, constitutional governance, worktree isolation. When I pitched it to engineering leadership, they didn't care. Because I pitched what I built, not why it matters.

### Arc
Open with the failure: preparing to discuss risk with senior engineering leadership, having all the project context from journals and sessions, and still pitching it wrong. The instinct was to present the tooling — the agents, the architecture, the test coverage. But engineering leaders don't care about your pipeline or your framework. They care about organizational capability gaps and their business consequences. Walk through the reframing: from "here's what I built" (9 bullet points of technical details) to "here's the capability gap and why it matters" (4 strategic topics in one sentence each). The four topics that landed: (1) We lack portfolio-wide visibility into security posture — data is fragmented. (2) Compliance models are changing from vulnerability tracking to demonstrable risk assessment with audit trails. This is a legal obligation. (3) Risk assessment is a scaling problem, not a headcount problem — AI agents compress hours into minutes, but the pitch is "augment analysts" not "replace analysts." (4) The audit trail gap — if a regulator asks "how did you assess this risk," most organizations can't answer with provenance. Close with the pattern: start with the organizational problem, not the solution. Frame technical work as evidence the problem is solvable, not as the thing you're presenting.

### Key Data Points
- First pitch: 9 technical bullet points (agents, metrics, architecture)
- Reframed pitch: 4 strategic topics, one sentence each
- Altitude shift: from implementation details (6 min runtime, 66 references, citation completeness) to capability gaps (portfolio visibility, compliance readiness, scaling constraints)
- Translation guide: "event sourcing" → "audit trail," "constitutional governance" → "enforceable quality standards," "worktree isolation" → invisible at this level
- Key insight: everything below the "why should leadership care" line is too low-level for this audience

### Source Material
- `~/journal/daily/2026-02-24.md` — Session 13 (journal review, risk communication discussion)
- `~/journal/learnings/risk-communication-across-organizational-levels.md` — Full pattern extraction

### Sensitivity Flags
- CRITICAL: Cannot reference CRA (Cyber Resilience Act) by name — this compliance framework could identify employer
- Reframe CRA as "a new compliance model requiring demonstrable risk assessment with audit trails"
- Must not name employer, team structure, or specific regulatory obligations
- The pattern (engineering → leadership translation) is generic and career-spanning — safe to frame as accumulated wisdom
- Avoid "Red Hat," "Product Security," or any org-chart details

---

## Draft

<!-- Write your first draft below this line -->
