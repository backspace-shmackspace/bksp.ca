# Prompts Are Aspirational. Filesystems Are Physical.

**Status:** APPROVED — awaiting first draft
**Approved:** 2026-02-24
**Lane:** // build
**Format:** Blog post
**Register:** Blended (Register 1 narrative hook → Register 2 pattern extraction)
**Pitch source:** `pitches/2026-02-24-pitches.md`

---

## Writing Guidance

### Hook
I told two AI agents to work on different parts of the codebase. I gave them clear instructions: "Don't touch files outside your scope." They collided anyway, overwriting each other's changes. So I stopped telling them what not to do and made it physically impossible for them to interfere.

### Arc
Open with the failure mode: parallel AI agents implementing a cross-repo plan, both given explicit instructions to stay within boundaries, both ignoring those boundaries when the code structure pulled them into shared files. The collision wasn't malicious or random. It was inevitable. Walk through the insight: prompts are aspirational (they express what you want), but filesystems are physical (they enforce what's possible). Introduce the fix: git worktrees create complete, separate copies of the repository. Agents working in different worktrees physically cannot touch each other's files. Even if an agent ignores instructions, the worktree boundary prevents damage. This is defense in depth: prevention (worktrees) plus detection (file boundary validation after merge). Close with the transferable principle: any time you can make a constraint structural rather than instructional, you should. It's the difference between "please don't break things" and "you can't break things."

### Key Data Points
- Problem: 2 parallel agents, 15+ prompt tokens of "stay in scope" instructions, still collided
- Root cause: agents followed code structure (shared dependencies) not boundaries (work group scope)
- Fix: git worktrees provide physical isolation (<1s per worktree, acceptable overhead)
- Defense layers: (1) worktrees prevent conflicts, (2) file boundary validation catches leaks
- Zerg framework inspiration: structural guarantees > instructions
- Outcome: shipped citation-completeness across 2 repos with 2016 + 72 tests passing, zero conflicts

### Source Material
- `~/journal/daily/2026-02-23.md` — Zerg analysis session, worktree isolation implementation, code review with 6 critical issues
- `~/journal/daily/2026-02-24.md` — Ship skill worktree isolation always-on (not just multi-group)
- `~/journal/learnings/structural-guarantees-over-instructions.md` — Core pattern extraction
- `~/journal/decisions/2026-02-23-worktree-isolation.md` — Adoption decision

### Sensitivity Flags
- Zerg framework is a public article (rockcybermusings.com) by another developer — safe to reference and credit
- Git worktrees are standard Git functionality — no employer-specific implementation
- Claude Code and /ship skill are public tools — safe to discuss
- No JIRA tickets, project names, or employer details needed for this pattern

---

## Draft

<!-- Write your first draft below this line -->
