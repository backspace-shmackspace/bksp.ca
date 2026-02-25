# Recovery Prioritization: Tools, Then Deployment, Then Features

**Status:** APPROVED — awaiting first draft
**Approved:** 2026-02-24
**Lane:** // defense
**Format:** LinkedIn post (short form)
**Register:** 2 (analytical/authority)
**Pitch source:** `pitches/2026-02-24-pitches.md`

---

## Writing Guidance

### Hook
After my MacBook died, I had a choice: jump back into building new features, or fix the broken tooling and deploy the operational systems first. The instinct was features. The right answer was plumbing.

### Arc
Open with the post-recovery temptation: hardware failure behind you, codebase recovered, natural instinct is to dive back into "interesting" work — new features, new architectures, new ideas. But without operational infrastructure, features can't be tested or validated. Present the recovery prioritization pattern: (1) Fix tooling first (shell detection bugs, Python compatibility, model naming). (2) Deploy operational systems (risk-orchestrator, agent-factory, helper MCPs). (3) Then build new features. Each layer depends on the previous. Skipping layers leads to partial systems and duplicated effort. Close with the outcome: followed the discipline, shipped prodsecrm operational by Feb 24, zero rework.

### Key Data Points
- Recovery context: MacBook failure, 18 repos, 507 commits recovered
- Tooling fixes: 4 bugs (shell detection, python3, model naming, deploy.sh)
- Deployment scope: risk-orchestrator (2016 tests), agent-factory (72 tests), helper MCPs (5+ servers)
- Feature work deferred: OpenShift AI migration, hallucination detection, security data federation
- Outcome: prodsecrm fully operational in 2 days by following the discipline
- Anti-pattern avoided: jumping to "interesting" feature work with broken infrastructure

### Source Material
- `~/journal/daily/2026-02-22.md` — Session 4 (bugfixes)
- `~/journal/daily/2026-02-23.md` — Recovery planning session
- `~/journal/daily/2026-02-24.md` — Deployment completion
- `~/journal/learnings/recovery-prioritization-pattern.md` — Pattern extraction
- `~/journal/PRIORITIES.md` — Priority 0 (recovery) vs Priority 1 (features)

### Sensitivity Flags
- Must not name employer or specific project names
- Frame as "a multi-agent risk assessment system" or "an AI-assisted security pipeline"
- The recovery pattern (tools → deployment → features) is generic and transferable — safe to discuss
- Claude Code, git workflows, and shell scripting bugs are public domain — safe to reference

---

## Draft

<!-- Write your first draft below this line -->
