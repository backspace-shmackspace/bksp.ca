---
name: review
description: Editorial + visual + sensitivity review (copy-editor + visual-designer + sensitivity-reviewer).
model: sonnet
---
# /review — Editorial, Visual, & Sensitivity Review

Run a comprehensive review on a draft before publishing: content quality (copy-editor), visual design (visual-designer), and sensitivity check (sensitivity-reviewer).

## Workflow

### Stage 1: Editorial Review (Copy-Editor)

1. Read the copy-editor agent at `.claude/agents/copy-editor.md`
2. Read the file specified in the arguments
3. Perform the full editorial review process:
   - Hook assessment
   - Structure & pacing
   - The "So What" test
   - Engagement potential (for LinkedIn) or reader value (for blog)
   - Voice alignment
   - **Callout identification** (blog posts only): Suggest 3-5 quotable snippets for blockquote/callout formatting
4. Output the review following the copy-editor's format
5. Save as `[filename].copy-review.md`

### Stage 2: Visual Design Review (Visual-Designer)

6. Read the visual-designer agent at `.claude/agents/visual-designer.md`
7. Read the same draft file
8. Identify 3-7 visual opportunities:
   - Hero image (required)
   - Inline diagrams (system architecture, flow charts, timelines)
   - Data visualizations (charts, graphs, tables)
   - Code screenshots (terminal output, config files)
   - Concept illustrations (abstract ideas made visual)
   - Social media card (required)
9. Output the visual specifications following the visual-designer's format
10. Save as `[filename].visual-specs.md`

### Stage 3: Sensitivity Review (Sensitivity-Reviewer)

11. Read the sensitivity-reviewer agent at `.claude/agents/sensitivity-reviewer.md`
12. Read the same draft file
13. Perform the full sensitivity review process (named entity scan, fingerprint analysis, employer exposure, career risk)
14. Output the review in the sensitivity-reviewer's format
15. Save as `[filename].sensitivity-review.md`

### Stage 4: Summary

16. Present a combined summary showing:
    - **Editorial Verdict:** [PUBLISH / REVISE / REWRITE]
    - **Visual Readiness:** [X visuals recommended] (hero image, Y diagrams, Z charts)
    - **Sensitivity Verdict:** [CLEAR / CAUTION / BLOCKED]
    - **Top 3 Editorial Issues** (from copy-editor)
    - **Top 3 Visual Opportunities** (from visual-designer)
    - **Top Sensitivity Risks** (from sensitivity-reviewer)
    - **Overall Recommendation:** Can this be published as-is, or what needs to change?

## Arguments

- Required: path to the draft file to review
  - Example: `/review drafts/linkedin/001-commitment-without-execution.md`
  - Example: `/review site/src/content/posts/hackthebox-to-boardroom.md`

## Notes

- Both reviews run sequentially — editorial first, then sensitivity
- This is a gate, not a blocker — Ian makes the final call on what to publish
- If either verdict is negative, explain clearly why and whether any rewrite could save it
- The copy-editor may suggest substantial rewrites; the sensitivity-reviewer may block publication entirely
- Both perspectives are valuable — quality and safety
