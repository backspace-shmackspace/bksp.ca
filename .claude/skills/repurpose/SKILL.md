# /repurpose — Transform Content Across Formats

Take a piece of content and create derivative versions for other platforms.

## Workflow

1. Read the repurposer agent at `.claude/agents/repurposer.md`
2. Read the master persona at `~/bksp/persona/master-persona.md`
3. Read the source content specified in arguments
4. Determine the appropriate transformation (blog → LinkedIn, LinkedIn → blog, HTB → defenders post)
5. Create the derivative content
6. Save to the appropriate directory under `~/bksp/drafts/`
7. Present the result to the user

## Arguments

- Required: path to the source content
- Optional: target format
  - `--linkedin`: create a LinkedIn post
  - `--blog`: create a blog post outline
  - `--carousel`: create a carousel outline
  - `--defenders`: (for HTB writeups) create a "lessons for defenders" post

If no target format specified, auto-detect the best transformation based on the source format.

## Examples

```
/repurpose site/src/content/posts/hackthebox-to-boardroom.md --linkedin
/repurpose drafts/linkedin/003-ai-red-team.md --blog
/repurpose site/src/content/posts/htb-jupiter-sql-injection-grafana.md --defenders
```
