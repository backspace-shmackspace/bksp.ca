# bksp_ Style Guide

## Punctuation Rules

### BANNED: Em-dashes (—)

**Never use em-dashes.** They're overused in AI-generated content and signal inauthenticity.

**Instead, use:**

1. **Periods.** Break into separate sentences.
   - ❌ "I found critical tickets—some over a year old—with no owner."
   - ✅ "I found critical tickets with no owner. Some were over a year old."

2. **Commas.** For less dramatic pauses.
   - ❌ "The gap is comfort—a risk on a register feels managed."
   - ✅ "The gap is comfort. A risk on a register feels managed."

3. **Parentheses.** For asides or clarifications.
   - ❌ "At IBM—where I led 80+ engineers—I drove DevSecOps transformation."
   - ✅ "At IBM (where I led 80+ engineers) I drove DevSecOps transformation."

4. **Colons.** For explanations or lists.
   - ❌ "I apply the same discipline—evidence-based scoping, quantified impact."
   - ✅ "I apply the same discipline: evidence-based scoping, quantified impact."

5. **Semicolons.** For related independent clauses.
   - ❌ "The system is broken—no one fixes it."
   - ✅ "The system is broken; no one fixes it."

6. **Just remove it.** Often the em-dash is unnecessary.
   - ❌ "Most risk programs—in my experience—run on intuition."
   - ✅ "Most risk programs run on intuition."

---

## Voice Principles

### Evidence-First
- Lead with data, not opinions
- Show the proof before the claim
- Quantify whenever possible

### Directly Decisive
- Commit to positions
- Avoid hedging ("perhaps," "maybe," "might")
- Say what you mean

### Quietly Contrarian
- Challenge conventional wisdom without shouting
- Frame as observation, not argument
- Let the evidence do the work

### Engineering Precision
- Be specific
- No vague business-speak ("synergy," "leverage," "optimize")
- Technical terms are fine; buzzwords are not

---

## Formatting

### Headings
- Use sentence case, not title case
- No colons at end of headings
- Keep short (under 8 words)

### Lists
- Parallel structure required
- Start each item with same part of speech
- Capitalize first word, no periods unless full sentences

### Code Blocks
- Always specify language for syntax highlighting
- Include comments only where non-obvious
- No unnecessary blank lines

### Callouts (Blog Posts)
- 1-2 sentences maximum
- Must be quotable out of context
- Should contain data, contrast, or tension
- No generic wisdom ("Quality matters")

---

## Banned Phrases

**AI tells:**
- "In today's landscape"
- "It's important to note that"
- "At the end of the day"
- "Dive deep into"
- "Unlock the power of"
- "Leverage synergies"
- "Needless to say"
- "To be honest" / "To be fair"
- "The fact of the matter is"

**Corporate jargon:**
- "Circle back"
- "Move the needle"
- "Low-hanging fruit"
- "Think outside the box"
- "Paradigm shift"
- "Best of breed"
- "Synergy"
- "Bandwidth" (unless discussing networks)

**Unnecessary hedging:**
- "I think that"
- "In my opinion"
- "It seems like"
- "Sort of" / "Kind of"
- "Pretty much"

---

## LinkedIn-Specific Rules

### Character Limits
- Headline: 220 characters max
- About section: 2,600 characters (aim for 1,200-1,500)
- Posts: No hard limit, but optimal is 1,200-2,000 characters

### Hook Rules (First 2 Lines)
- Must work before the "see more" fold
- Create tension, curiosity, or pattern interruption
- No throat-clearing ("I spent 20 years...")
- No credentials up front
- No definitions

### Engagement Design
- End with specific, actionable challenge (not "What do you think?")
- Stake a position someone can debate
- Make it easy to comment with a concrete response

### Hashtags
- 2-3 maximum
- Place at very end
- No hashtag stuffing

---

## Blog Post Rules

### Structure
- Hook in first paragraph (8-second rule)
- Use subheadings every 300-400 words
- Include 3-5 callouts for pull quotes
- End with actionable takeaway, not summary

### Technical Content
- Code examples must be tested and functional
- Include prerequisites if commands assume setup
- Explain "why" not just "what"
- No "just" or "simply" (if it were simple, they wouldn't need the guide)

### Sensitivity (CRITICAL)
- No employer names (except in bio/about page when discussing career)
- No people names
- No project identifiers
- Frame as career-spanning patterns, not specific instances
- Run `/review` before publishing

---

## HTB Writeup Rules

### Voice: Conversational, tutorial-style
- "Let's see what we can do"
- Show dead ends and reasoning
- Walk through methodology, not just results

### Structure
- Enumeration → Foothold → User → Root
- Show nmap/scan output
- Explain tools and techniques
- Include lessons learned

### Screenshots
- Must be readable (no tiny terminal text)
- Crop to relevant content
- Syntax highlighting where possible

---

## When in Doubt

1. **Read it out loud.** Does it sound like Ian, or like a LinkedIn influencer?
2. **Remove intensifiers.** "Very," "really," "incredibly" usually weaken writing.
3. **Cut the first paragraph.** Often the real hook is buried in paragraph 2.
4. **Replace adjectives with data.** "Significant" → "52%". "Many" → "38 out of 40".
5. **Check for em-dashes.** Remove every single one.

---

## Examples

### Bad (AI voice)
> "In today's rapidly evolving cybersecurity landscape, it's important to note that organizations are increasingly leveraging AI-powered solutions to unlock the power of automated risk management—but many are still struggling to move the needle on actually implementing these tools effectively."

**Problems:** Em-dashes, buzzwords, hedging, no specifics.

### Good (Ian's voice)
> "Most risk teams buy AI tools and never use them. I found 14 products in our compliance stack. Only 3 had active integrations. The rest were shelfware with annual renewals."

**Why it works:** Specific data, no jargon, direct, evidence-first.

---

## Enforcement

- **Copy-editor agent:** Flags em-dashes, banned phrases, and voice drift
- **Sensitivity-reviewer agent:** Ensures anonymization before publishing
- **All agents:** Must follow this style guide when drafting or editing content

---

**Last updated:** 2026-02-18
