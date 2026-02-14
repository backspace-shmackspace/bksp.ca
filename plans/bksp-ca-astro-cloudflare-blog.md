# Technical Implementation Plan: bksp.ca — Astro Blog on Cloudflare Pages

**Feature:** Build the bksp.ca personal blog with terminal/brutalist aesthetic
**Created:** 2026-02-14
**Author:** Architect (coordinator-drafted, no project-specific senior-architect)

---

## Goals

1. Build a static blog at bksp.ca using Astro, styled with a terminal/brutalist aesthetic consistent with the `bksp_` brand
2. Deploy on Cloudflare Pages with git-push CI/CD ($0/month hosting)
3. Support three content lanes: `// Offense`, `// Defense`, `// Build`
4. Source content from markdown files with YAML frontmatter
5. Provide an About page featuring HTB credentials and professional bio
6. Enable cross-posting workflow (canonical on bksp.ca, syndicate to Medium/LinkedIn)

## Non-Goals

- No CMS or admin interface (content is markdown in git)
- No comments system in v1 (add later if needed via Giscus or similar)
- No newsletter/email capture in v1 (add Buttondown or similar later)
- No analytics in v1 (add Cloudflare Web Analytics later — free, privacy-respecting)
- No client-side JavaScript unless absolutely necessary (static-first)
- No RSS in v1 scope (add `@astrojs/rss` in v2)
- No sitemap in v1 scope (add `@astrojs/sitemap` in v2)

## Assumptions

1. Ian has Astro experience from risk-docs-site (confirmed — same stack, same patterns)
2. bksp.ca domain is registered and DNS can be pointed to Cloudflare
3. Content drafts already exist in `~/bksp/drafts/` (4 LinkedIn posts, 1 blog post)
4. Cloudflare account exists or can be created (free tier)
5. Git repository will be hosted on GitHub (public — blog is public content)
6. Inter for body/headings, JetBrains Mono for code blocks only

## Proposed Design

### Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Framework | Astro 5.x | Proven in risk-docs-site, static-first, markdown-native |
| Styling | Tailwind CSS 4.x | Proven in risk-docs-site, utility-first |
| Font (body) | Inter | Clean, modern, highly legible sans-serif |
| Font (code) | JetBrains Mono | Terminal feel for code blocks and commands |
| Content | Astro Content Collections | Built-in, type-safe, frontmatter validation via Zod |
| Hosting | Cloudflare Pages | $0, unlimited bandwidth, global CDN, git-push deploy |
| DNS | Cloudflare DNS | Free, integrates with Pages, fast propagation |
| SSL | Cloudflare (automatic) | Free, auto-provisioned for custom domains |
| Repository | GitHub (public) | Cloudflare Pages has native GitHub integration |

### Content Architecture

```
src/content/
  posts/
    001-commitment-without-execution.md      # // Defense
    002-quantify-or-kill.md                  # // Defense
    003-ai-red-team.md                       # // Build
    hackthebox-to-boardroom.md               # // Defense
    htb-jupiter-sql-injection-grafana.md     # // Offense (existing Medium post)
    htb-active-windows-misconfig.md          # // Offense (existing Medium post)
    htb-ghoul.md                             # // Offense (existing Medium post)
```

### Frontmatter Schema

```yaml
---
title: "The Commitment-Without-Execution Loop"
slug: "commitment-without-execution"
date: 2026-02-18
lane: "defense"           # offense | defense | build
description: "Why critical security risks cycle through corporate commitment theater for years without resolution."
tags: ["risk-management", "security-leadership", "organizational-patterns"]
featured: true             # Show on homepage hero
draft: false               # Exclude from build when true
canonical_url: ""          # Set if cross-posted FROM another site
---
```

### Route Structure

| URL | Page | Description |
|---|---|---|
| `bksp.ca/` | Homepage | Hero + latest posts across all lanes |
| `bksp.ca/offense/` | Lane index | All // Offense posts |
| `bksp.ca/defense/` | Lane index | All // Defense posts |
| `bksp.ca/build/` | Lane index | All // Build posts |
| `bksp.ca/posts/[slug]` | Post detail | Individual blog post |
| `bksp.ca/about` | About page | Bio, HTB stats, credibility stack |
| `bksp.ca/tags/[tag]` | Tag index | Posts filtered by tag |

### Visual Design

**Design direction:** Modern, sleek, cybersecurity-focused. Think CrowdStrike/Wiz/Snyk — dark theme, clean lines, subtle depth, professional but technical. Not brutalist.

**Brand identity:**
- Logo: `bksp_` in Inter (bold) with underscore cursor animation (CSS blink)
- Color palette: dark navy/charcoal base, not pure black
  - Background: `#0a0f1a` (deep navy), cards: `#111827` (slate-900)
  - Text: `#f1f5f9` (slate-100), secondary: `#94a3b8` (slate-400)
- Primary accent: `#3b82f6` (blue-500) — links, active states, CTAs
- Lane accents:
  - `// Offense`: `#ef4444` (red-500)
  - `// Defense`: `#3b82f6` (blue-500)
  - `// Build`: `#8b5cf6` (violet-500)
- Subtle gradients on hero and featured cards (dark → slightly lighter)
- Rounded corners (`rounded-lg`, `rounded-xl`) — modern, not brutalist
- Cards with `border border-slate-800` and subtle `hover:border-slate-600` transitions
- Glass morphism on header: `backdrop-blur-md bg-slate-900/80`
- Smooth transitions on hover states (`transition-all duration-200`)

**Typography:**
- Headings: Inter (bold/semibold) — clean, modern, highly legible
- Body: Inter (regular) — professional readability
- Code blocks: JetBrains Mono — terminal feel only where appropriate (code, commands)
- Line height: 1.75 for body text (spacious, modern)

**Homepage layout:**
```
┌─────────────────────────────────────────┐
│ bksp_          offense defense build  ↗ │  ← sticky glass header
├─────────────────────────────────────────┤
│                                         │
│  bksp_                                  │
│  undoing what shouldn't have shipped    │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  FEATURED · // defense            │  │  ← gradient border card
│  │  The Commitment-Without-Execution │  │
│  │  Loop                             │  │
│  │  Why critical security risks...   │  │
│  │  4 min read →                     │  │
│  └───────────────────────────────────┘  │
│                                         │
│  Latest                                 │
│  ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ // build │ │//defense │ │//offens│  │  ← hover-lift cards
│  │ AI Red   │ │ Quantify │ │ HTB    │  │
│  │ Team...  │ │ or Kill  │ │ Jupiter│  │
│  │ 5 min →  │ │ 3 min →  │ │ 11 min→│  │
│  └──────────┘ └──────────┘ └────────┘  │
│                                         │
├─────────────────────────────────────────┤
│ bksp_ © 2026    github · htb · linkedin│  ← subtle footer
└─────────────────────────────────────────┘
```

**Post page layout:**
```
┌─────────────────────────────────────────┐
│ bksp_          offense defense build  ↗ │
├─────────────────────────────────────────┤
│                                         │
│  // defense                             │
│                                         │
│  The Commitment-Without-Execution Loop  │  ← large, bold heading
│                                         │
│  Feb 18, 2026 · 4 min read             │  ← muted meta line
│  ┌────────┐ ┌───────────────────┐       │
│  │ risk   │ │ security-leader.. │       │  ← pill-shaped tags
│  └────────┘ └───────────────────┘       │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │  ← subtle divider
│                                         │
│  Post content in clean readable         │
│  typography. Code blocks have dark      │
│  backgrounds with syntax highlighting   │
│  and rounded corners...                 │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ ```bash                           │  │  ← styled code blocks
│  │ nmap -sC -sV 10.129.173.236      │  │
│  │ ```                               │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│  ← Previous Post       Next Post →     │
│                                         │
├─────────────────────────────────────────┤
│ bksp_ © 2026    github · htb · linkedin│
└─────────────────────────────────────────┘
```

**About page content:**
- Short bio (engineer → risk → hacking)
- HTB stats block (Omniscient, #906, 94 machines, 231 flags, Pro Labs)
- Content lanes explanation
- Links: HTB profile, Medium/InfoSec Write-ups, LinkedIn, GitHub

### Component Inventory

| Component | Purpose |
|---|---|
| `BaseLayout.astro` | HTML shell, head tags, header, footer, global styles |
| `Header.astro` | `bksp_` logo + nav (lanes + about) |
| `Footer.astro` | Copyright + social links |
| `PostCard.astro` | Post preview card for index pages |
| `PostLayout.astro` | Blog post wrapper (title, date, tags, prev/next) |
| `LaneBadge.astro` | Colored lane indicator (offense/defense/build) |
| `TagList.astro` | Clickable tag pills |
| `ReadingTime.astro` | Calculated reading time display |
| `HtbStats.astro` | HTB credential block for about page |
| `OpenGraph.astro` | OG meta tags for LinkedIn/social sharing previews |

## Interfaces / Schema Changes

### Content Collection Schema (`src/content/config.ts`)

```typescript
import { defineCollection, z } from 'astro:content';

const posts = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    lane: z.enum(['offense', 'defense', 'build']),
    description: z.string(),
    tags: z.array(z.string()).default([]),
    featured: z.boolean().default(false),
    draft: z.boolean().default(false),
    canonical_url: z.string().url().optional(),
  }),
});

export const collections = { posts };
```

## Data Migration

- Move blog draft from `~/bksp/drafts/blog/001-hackthebox-to-boardroom.md` into `src/content/posts/` with proper frontmatter
- LinkedIn posts are NOT migrated (they are platform-specific short-form content, not blog posts)
- Existing Medium HTB writeups can be added later as `// Offense` posts with `canonical_url` pointing to Medium originals

## Rollout Plan

### Phase 1: Scaffold (this session)

1. Initialize Astro project in `~/bksp/site/`
2. Configure Tailwind with dark cybersecurity theme
3. Create BaseLayout, Header, Footer components
4. Create content collection schema
5. Build homepage with placeholder content
6. Build post detail page
7. Build lane index pages (offense/defense/build)
8. Build about page
9. Add first blog post (hackthebox-to-boardroom)
10. Local dev verification (`npm run dev`)

### Phase 2: Deploy

1. Initialize git repo, push to GitHub
2. Connect GitHub repo to Cloudflare Pages
3. Configure build settings (Astro adapter)
4. Add bksp.ca custom domain in Cloudflare Pages
5. Point bksp.ca DNS to Cloudflare Pages
6. Verify SSL and live site
7. Test all routes on production

### Phase 3: Content Population (post-deploy)

1. Add existing Medium HTB writeups as `// Offense` posts
2. Convert LinkedIn drafts to blog format if desired
3. Establish posting workflow (write markdown → git push → auto-deploy)

## Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| DNS propagation delay | Site not reachable for up to 48h | Medium | Use Cloudflare DNS (fast propagation, usually <1h) |
| Cloudflare Pages build failure | Deploy blocked | Low | Astro + Cloudflare is well-documented; use `@astrojs/cloudflare` adapter only if SSR needed (not needed for static) |
| Content accidentally includes sensitive info | Employer exposure | Medium | Sensitivity review process already established in persona/master-persona.md; all content reviewed before commit |
| Scope creep (comments, newsletter, analytics) | Delays launch | Medium | Explicitly non-goals for v1; ship the static blog first |

## Test Plan

### Build Verification

```bash
cd ~/bksp/site
npm run build
```

**Pass criteria:** Build completes with zero errors, `dist/` directory contains all expected routes.

### Local Preview

```bash
npm run preview
```

**Manual checks:**
- [ ] Homepage renders with `bksp_` header and post cards
- [ ] Each lane index page (/offense, /defense, /build) shows filtered posts
- [ ] Post detail page renders markdown correctly with code blocks
- [ ] About page shows HTB stats
- [ ] Navigation works between all pages
- [ ] Mobile responsive (check at 375px width)
- [ ] Print stylesheet hides nav/footer, clean output
- [ ] No client-side JavaScript errors in console
- [ ] Draft posts excluded from production build

### Content Validation

```bash
npx astro check
```

**Pass criteria:** Zero TypeScript errors, all frontmatter validates against Zod schema.

### Production Verification (post-deploy)

- [ ] bksp.ca resolves with valid SSL
- [ ] All routes return 200
- [ ] Open Graph meta tags present (for LinkedIn sharing)
- [ ] Page load time <2s on mobile (Cloudflare CDN should ensure this)

## Acceptance Criteria

1. `bksp.ca` serves a static Astro blog with the modern/sleek cybersecurity aesthetic
2. At least one blog post ("From HackTheBox to the Boardroom") is live and readable
3. Three content lane pages exist and filter correctly
4. About page displays HTB credentials and bio
5. Git-push to main triggers automatic Cloudflare Pages deploy
6. Total hosting cost: $0/month
7. Build completes in under 60 seconds
8. Site scores 90+ on Lighthouse performance audit

## Task Breakdown

### Files to Create

```
~/bksp/site/
  package.json                          # Dependencies and scripts
  astro.config.mjs                      # Astro configuration (static output)
  tailwind.config.mjs                   # Dark cyber theme (colors, fonts, borders)
  tsconfig.json                         # TypeScript configuration
  .gitignore                            # Node modules, dist, .astro
  public/
    favicon.svg                         # bksp_ favicon (terminal cursor)
  src/
    env.d.ts                            # Astro environment types
    styles/
      global.css                        # Tailwind directives + global overrides
    content/
      config.ts                         # Content collection schema (Zod)
      posts/
        hackthebox-to-boardroom.md      # First blog post
    layouts/
      BaseLayout.astro                  # HTML shell, head, meta, OG tags
      PostLayout.astro                  # Blog post wrapper
    components/
      Header.astro                      # bksp_ logo + navigation
      Footer.astro                      # Copyright + social links
      PostCard.astro                    # Post preview card
      LaneBadge.astro                   # Lane indicator (offense/defense/build)
      TagList.astro                     # Clickable tags
      ReadingTime.astro                 # Reading time calculation
      HtbStats.astro                    # HTB credential block
    pages/
      index.astro                       # Homepage
      about.astro                       # About page
      offense/
        index.astro                     # // Offense lane index
      defense/
        index.astro                     # // Defense lane index
      build/
        index.astro                     # // Build lane index
      posts/
        [...slug].astro                 # Dynamic post detail page
      tags/
        [tag].astro                     # Tag filter page
      404.astro                         # Custom 404 page
```

### Files to Modify

- `~/bksp/drafts/blog/001-hackthebox-to-boardroom.md` — Extract post body, add proper frontmatter, copy to `src/content/posts/`

### Implementation Order

1. `package.json` + `npm install`
2. `astro.config.mjs` + `tsconfig.json` + `env.d.ts`
3. `tailwind.config.mjs` + `src/styles/global.css`
4. `public/favicon.svg`
5. `src/content/config.ts` (schema)
6. `src/content/posts/hackthebox-to-boardroom.md` (first post)
7. `src/layouts/BaseLayout.astro`
8. `src/components/Header.astro` + `Footer.astro`
9. `src/components/LaneBadge.astro` + `TagList.astro` + `ReadingTime.astro`
10. `src/components/PostCard.astro`
11. `src/pages/index.astro` (homepage)
12. `src/layouts/PostLayout.astro`
13. `src/pages/posts/[...slug].astro` (post detail)
14. `src/pages/offense/index.astro` + `defense/index.astro` + `build/index.astro`
15. `src/components/HtbStats.astro`
16. `src/pages/about.astro`
17. `src/pages/tags/[tag].astro`
18. `.gitignore`
19. Local build + preview verification
20. Git init + GitHub push
21. Cloudflare Pages connection + custom domain
22. Production verification

## Hosting Cost Breakdown

| Service | Cost | Notes |
|---|---|---|
| Cloudflare Pages | $0 | Unlimited bandwidth, 500 builds/month on free tier |
| Cloudflare DNS | $0 | Free DNS hosting |
| Cloudflare SSL | $0 | Auto-provisioned for custom domains |
| Domain (bksp.ca) | Already owned | Annual renewal only |
| GitHub repo | $0 | Public repository |
| **Total monthly** | **$0** | |

## Status: APPROVED
