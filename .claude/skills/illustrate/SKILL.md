---
name: illustrate
description: Generate visual design specifications (diagrams, charts, hero images) for a blog post.
model: sonnet
---
# /illustrate — Visual Design Specifications

Generate visual design specifications for a blog post or article without running the full review workflow.

## Workflow

1. Read the visual-designer agent at `.claude/agents/visual-designer.md`
2. Read the file specified in the arguments
3. Identify 3-7 visual opportunities:
   - **Hero image** (required) — Main image at top of post
   - **Inline diagrams** — System architecture, flow charts, timelines
   - **Data visualizations** — Charts, graphs, comparison tables
   - **Code screenshots** — Terminal output, config files, diffs
   - **Concept illustrations** — Abstract ideas made visual
   - **Social media card** (required) — 1200x630px Open Graph image
4. For each visual, provide:
   - **Type** and **location** in the post
   - **Purpose** (what concept it clarifies)
   - **Detailed specification** (what to show, how to show it)
   - **Suggested tool** (Mermaid.js, Excalidraw, Chart.js, Carbon.sh, etc.)
   - **Implementation code** (when applicable — Mermaid syntax, Observable Plot code, etc.)
   - **Alternative approach** (if primary isn't feasible)
5. Output the visual specifications following the visual-designer's format
6. Save as `[filename].visual-specs.md`

## Arguments

- Required: path to the draft file
  - Example: `/illustrate drafts/blog/from-gemini-to-10-agents.md`
  - Example: `/illustrate site/src/content/posts/flow-engineering.md`

## Output Format

The visual-specs file will include:
- Hero image concept with sourcing suggestions
- 2-4 inline visual opportunities with implementation specs
- Social media card design
- Mermaid.js/Observable Plot code where applicable
- Tool recommendations and alternatives

## Use Cases

**When to use /illustrate instead of /review:**
- Content is already reviewed and approved, you just need visuals
- You want to add diagrams to an existing published post
- You're planning visuals before writing (visual-first approach)
- You want to iterate on visual concepts separately from content edits

**When to use /review instead:**
- Draft needs editorial feedback AND visual specs
- First-time review of new content
- You want copy-editor + visual-designer + sensitivity-reviewer all at once

## Notes

- Visual specs are recommendations, not requirements
- Implementation is manual (visuals must be created separately using suggested tools)
- Mermaid.js diagrams can be embedded directly in Markdown
- For Astro/MDX posts, Observable Plot code can be integrated as components
- Keep source files (.excalidraw, .mmd, .svg) for future edits
