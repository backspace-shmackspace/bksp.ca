# LinkedIn Post #2: Quantify or Kill

**Status:** DRAFT
**Created:** 2026-02-14
**Target:** LinkedIn (text post)
**Register:** 2 (analytical/authority)
**Follows:** Post #1 (Commitment-Without-Execution Loop)
**Character count:** ~1,500
**Hashtags:** #SecurityLeadership #RiskManagement

---

In software engineering, if a bug can't be reproduced, you close it. You don't carry an unreproducible bug on your backlog for two years "just in case."

Risk management doesn't have this discipline. I've inherited risk registers where critical-severity tickets had been open for over a year with no concrete evidence of impact, no quantified exposure, and no definition of what "mitigated" would even look like. Just a vague description and a long comment thread of people agreeing it's important.

When I moved from engineering into risk, I brought a rule with me:

**Quantify or kill. Two weeks.**

Here's how it works:

**Quantify:** Gather concrete evidence that makes the risk tangible. Not "this could be bad" — but specific data. How many systems are affected? What's the actual exposure? Can you show three real examples? If you can produce evidence, you now have an actionable risk with a measurable scope. Assign an owner, set acceptance criteria, allocate resources, track it like a production incident.

**Kill:** If two weeks of focused evidence gathering doesn't yield actionable scope, close the ticket. Not "defer." Not "move to monitoring." Close it. Write a one-paragraph rationale and move on.

Why two weeks? Because poorly-scoped risks are attention sinks. Every minute spent discussing a risk nobody can quantify is a minute not spent on the three risks you CAN quantify and ARE actively being exploited.

The pushback I get from career risk managers: "But what if we close it and something happens?"

My answer: What's happening RIGHT NOW while this vaguely-defined ticket consumes meeting time and mental bandwidth? The risks you're neglecting because your register is full of noise — those are the ones that will bite you.

A risk register isn't a collection of everything that might go wrong. It's a prioritized queue of quantified threats with owners and deadlines. Anything that can't meet that standard is noise.

Your register should be short, sharp, and fully resourced. Not long, vague, and ignored.

---

## Posting Notes

- Post 3-5 days after Post #1 to build momentum
- This one will generate disagreement from GRC/compliance professionals — that's engagement fuel
- No outbound link in main post
- First comment: "This pairs with my previous post on the Commitment-Without-Execution Loop — risks that can't be quantified are the ones most likely to cycle through that pattern indefinitely."

---

## Sensitivity Review

| Element | Source | Risk | Status |
|---|---|---|---|
| "Two weeks" deadline | 1:1 with Vince re: PRODSECRM-105 | Generic enough — common sprint duration | Safe |
| "Over a year" | General observation | No specific ticket identifiable | Safe |
| "Three real examples" | PRODSECRM-105 evidence requirement | Anonymized to generic advice | Safe |
| "Career risk managers" pushback | General framing | Not attributable to any individual | Safe |
| Bug reproduction analogy | Engineering background | Universal engineering concept | Safe |
| No people, companies, projects | — | — | Safe |

**No flags raised.** The "quantify or kill" framework is presented as a personal methodology. No specific risk, ticket, or organization is identifiable.

## Content Strategy Notes

- Post #1 (problem): The Commitment-Without-Execution Loop
- **Post #2 (solution): Quantify or Kill** <-- this post
- Post #3 (capability): "I built an AI red team that argues with itself" — shifts to the // Build lane
