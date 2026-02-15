---
name: mine
description: Mine journals for content pitches (3-5 per session).
model: sonnet
---
# /mine — Content Mining

Mine journal entries and work logs for content ideas.

## Workflow

1. Read the content-miner agent at `.claude/agents/content-miner.md`
2. Follow the agent's interaction model exactly:
   - Read `~/bksp/persona/master-persona.md` for voice and sensitivity rules
   - Check `~/bksp/drafts/` and `~/bksp/site/src/content/posts/` for existing content (avoid duplicates)
   - Scan recent journal entries (last 14 days first, expand if needed)
   - Scan ideas, brain reports, and project docs
   - Cross-reference against the three content lanes (offense/defense/build)
3. Produce 3-5 pitches in the format specified by the agent
4. Save to `~/bksp/pitches/YYYY-MM-DD-pitches.md`
5. Present a summary of pitches to the user

## Arguments

- No arguments: mine last 14 days of journal entries
- `--deep`: expand to all available journal entries and source material
- `--lane [offense|defense|build]`: focus on a specific content lane
