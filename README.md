# bksp_

Personal blog and content project for bksp.ca

## Structure

```
bksp/
  .claude/
    agents/
      content-miner.md      # Mines journals for content ideas
      sensitivity-reviewer.md # Pre-publish sensitivity gate
      repurposer.md          # Transforms content across formats
      publisher.md           # Build, deploy, commit workflow
    skills/
      mine/                  # /mine — generate content pitches
      review/                # /review — sensitivity check a draft
      repurpose/             # /repurpose — create derivative content
      publish/               # /publish — deploy to bksp.ca
      pitch-review/          # /pitch-review — manage the pitch pipeline
  persona/
    master-persona.md        # Voice, audience, sensitivity rules
  pitches/                   # Content pitches from /mine
  drafts/
    linkedin/                # LinkedIn post drafts
    blog/                    # Blog post drafts
  site/                      # Astro static site (bksp.ca)
```

## Content Lanes

- **// Offense** — HTB writeups, CTF walkthroughs, vulnerability research
- **// Defense** — Risk engineering, organizational patterns, compliance reality
- **// Build** — AI agent architecture, tooling, flow engineering

## Workflow

```
/mine → pitches → /pitch-review → approved skeleton
                                        ↓
                              Ian writes first draft
                                        ↓
                           copywriter/editor refines
                                        ↓
                              /review → sensitivity check
                                        ↓
                              /publish → live on bksp.ca
                                        ↓
                           /repurpose → LinkedIn, carousel, etc.
```

## Skills

| Skill | Purpose |
|---|---|
| `/mine` | Mine journals and work logs for content ideas (3-5 pitches) |
| `/pitch-review` | Browse, approve, develop, or kill pitches |
| `/review [path]` | Run sensitivity review on a draft |
| `/repurpose [path]` | Transform content to another format |
| `/publish [path]` | Build, deploy to Cloudflare Pages, commit and push |

## Deploy

```bash
cd ~/bksp/site
node node_modules/.bin/astro build && wrangler pages deploy dist --project-name bksp-ca
```
