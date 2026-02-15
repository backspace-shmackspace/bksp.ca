# /review — Sensitivity Review

Run a sensitivity review on a draft before publishing.

## Workflow

1. Read the sensitivity-reviewer agent at `.claude/agents/sensitivity-reviewer.md`
2. Read the file specified in the arguments
3. Perform the full review process (named entity scan, fingerprint analysis, employer exposure, career risk)
4. Output the review in the agent's format
5. Save the review alongside the draft as `[filename].review.md`

## Arguments

- Required: path to the draft file to review
  - Example: `/review drafts/linkedin/001-commitment-without-execution.md`
  - Example: `/review site/src/content/posts/hackthebox-to-boardroom.md`

## Notes

- This is a gate, not a blocker — Ian makes the final call on what to publish
- If the verdict is BLOCKED, explain clearly why and whether any rewrite could save it
