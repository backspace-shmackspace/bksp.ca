---
name: publish
description: Build, deploy, commit, and push content to bksp.ca.
model: sonnet
---
# /publish — Build, Deploy, and Commit

Publish content to bksp.ca.

## Workflow

1. Read the publisher agent at `.claude/agents/publisher.md`
2. If a draft path is provided as an argument:
   - Copy/move the draft to `~/bksp/site/src/content/posts/` with proper frontmatter
   - Verify frontmatter is complete and `draft: false`
3. Run the pre-publish checklist from the publisher agent
4. Execute the publish workflow:
   ```bash
   cd ~/bksp/site
   node node_modules/.bin/astro build
   wrangler pages deploy dist --project-name bksp-ca
   ```
5. Commit and push:
   ```bash
   cd ~/bksp
   git add site/src/content/posts/
   git commit -m "publish: [post title]"
   git push origin main
   ```
6. Output the live URLs

## Arguments

- No arguments: build and deploy whatever is currently in the site (rebuild/redeploy)
- Path to a draft: prepare the draft for publication, then build and deploy
  - Example: `/publish drafts/blog/002-flow-engineering.md`

## Notes

- Will NOT publish posts with `draft: true` — change to `false` first
- Will warn if build fails and will NOT deploy a broken build
- Will warn if the post is marked `featured: true` and another post already has that flag
