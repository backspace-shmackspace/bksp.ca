# bksp_ — Personal Cybersecurity Blog

**Site:** https://bksp.ca
**Repo:** https://github.com/backspace-shmackspace/bksp.ca
**Hosting:** Cloudflare Pages (free tier, deploy via wrangler CLI)
**Stack:** Astro 5, Tailwind CSS, Inter + JetBrains Mono fonts

## Quick Start

```bash
cd ~/bksp/site

# Local dev
node node_modules/.bin/astro dev

# Build + deploy
node node_modules/.bin/astro build && wrangler pages deploy dist --project-name bksp-ca

# Push to GitHub
cd ~/bksp && git push origin main
```

**GitHub remote uses SSH alias:** `git@github-personal:backspace-shmackspace/bksp.ca.git`
This routes through the `github-personal` host in `~/.ssh/config` to the backspace-shmackspace account (not imurphy-rh).

## Content Architecture

### Three Lanes

| Lane | Slug | Content |
|---|---|---|
| **// Offense** | `/offense` | HTB writeups, CTF walkthroughs, vulnerability research |
| **// Defense** | `/defense` | Risk engineering, organizational patterns, compliance reality |
| **// Build** | `/build` | AI agent architecture, security tooling, flow engineering |

### Adding a New Post

1. Create `site/src/content/posts/[slug].md` with frontmatter:
   ```yaml
   ---
   title: "Post Title"
   date: YYYY-MM-DD
   lane: "offense" | "defense" | "build"
   description: "Under 160 chars for SEO/OG"
   tags: ["tag-1", "tag-2"]
   featured: false
   draft: false
   canonical_url: ""  # set if cross-posted from elsewhere
   ---
   ```
2. Write markdown body below frontmatter
3. Build and deploy (see Quick Start)

### Content Schema

Validated by Zod in `site/src/content/config.ts`. Build will fail if frontmatter is invalid.

## Content Pipeline

```
/mine → pitches → /pitch-review → approved skeleton
                                       ↓
                             write first draft
                                       ↓
                          copywriter/editor refines
                                       ↓
                             /review → sensitivity check
                                       ↓
                             /publish → live on bksp.ca
                                       ↓
                          /repurpose → LinkedIn, carousel
```

## Skills

| Skill | Location | Purpose |
|---|---|---|
| `/mine` | `.claude/skills/mine/` | Mine journals for content pitches (3-5 per session) |
| `/pitch-review` | `.claude/skills/pitch-review/` | Browse, approve, develop, or kill pitches |
| `/review [path]` | `.claude/skills/review/` | Run sensitivity review before publishing |
| `/repurpose [path]` | `.claude/skills/repurpose/` | Transform content across formats |
| `/publish [path]` | `.claude/skills/publish/` | Build, deploy, commit, push |

**Note:** Skills are project-local. Run from `~/bksp`. If skill invocation fails, follow the SKILL.md instructions manually.

## Agents

| Agent | Location | Role |
|---|---|---|
| **content-miner** | `.claude/agents/content-miner.md` | Digs through journals for story ideas |
| **sensitivity-reviewer** | `.claude/agents/sensitivity-reviewer.md` | Pre-publish anonymization gate |
| **repurposer** | `.claude/agents/repurposer.md` | Blog → LinkedIn, HTB → defenders, etc. |
| **publisher** | `.claude/agents/publisher.md` | Build/deploy/commit workflow |

## Key Directories

```
~/bksp/
  .claude/agents/          # Agent definitions
  .claude/skills/          # Skill definitions
  persona/
    master-persona.md      # Voice, audience, sensitivity protocol — READ THIS FIRST
  pitches/                 # Content pitches from /mine
  drafts/
    linkedin/              # LinkedIn post drafts (numbered)
    blog/                  # Blog post drafts
  reference/               # Source material (Gemini retrospective, etc.)
  site/                    # Astro static site
    src/content/posts/     # Published blog posts (markdown)
    src/components/        # Astro components
    src/layouts/           # Page layouts
    src/pages/             # Route pages
    dist/                  # Build output (not committed)
```

## Sensitivity Protocol (CRITICAL)

Ian works at Red Hat. All content must be anonymized before publishing. Key rules:

1. **No names** of people, clients, projects, JIRA tickets
2. **No employer-identifiable details** (platforms, compliance gaps, vendor products)
3. **No research shared internally** by colleagues (even if publicly available)
4. **Extract patterns, not instances** — frame as career-spanning observations
5. **Run `/review` before publishing** any new content

Full protocol in `persona/master-persona.md`.

## Voice (Two Registers)

**Register 1 — "The Walkthrough":** Conversational, tutorial-style. "Let's see what we can do." For HTB writeups and technical content.

**Register 2 — "The Analysis":** Structured, evidence-first, data-backed. For LinkedIn posts and risk management pieces.

Full voice guide in `persona/master-persona.md`.

## Social Links

| Platform | URL |
|---|---|
| Blog | https://bksp.ca |
| GitHub | https://github.com/backspace-shmackspace |
| HackTheBox | https://app.hackthebox.com/users/68192 |
| LinkedIn | https://www.linkedin.com/in/ian-murphy-nb/ |
| InfoSec Write-ups | https://infosecwriteups.com |

## Published Content

### Blog Posts (bksp.ca)
- From HackTheBox to the Boardroom (// defense, featured)
- SQL Injection by Default in Grafana — HTB Jupiter (// offense)
- Abusing Common Windows Misconfigurations — HTB Active (// offense)
- HackTheBox WriteUp — Ghoul (// offense)

### LinkedIn Drafts (ready to post)
- 001: The Commitment-Without-Execution Loop
- 002: Quantify or Kill
- 003: I Built an AI Red Team That Argues With Itself
- 004: From HackTheBox to the Boardroom (blog excerpt)

### Content Pitches (in pipeline)
See `pitches/2026-02-15-pitches.md` for 5 active pitches.

## HTB Credentials (for About page / bio)

- **Rank:** Omniscient (#906 global)
- **Hall of Fame:** Top 10 (achieved)
- **Completionist:** 100% completion (achieved)
- **Machines:** 94 owned
- **Flags:** 231
- **Pro Labs:** Chasm, Guardian, Messenger, BackTrack
- **Member since:** September 2018
