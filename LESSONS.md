# LESSONS.md — what we learned the hard way

An **append-only** log of non-obvious things discovered while building this project.
This is the project's memory. When you hit a surprise — a library that didn't behave, a
tax rule that wasn't what the README assumed, an architectural choice that turned out
wrong — you write it down here so the next agent (and the owner) doesn't pay for it twice.

This pairs with the learning mandate in `CLAUDE.md` §0: the **How & Why** in your reply
explains *this* change; `LESSONS.md` captures the *transferable* insight that outlives it.

## When to add an entry

Add one when:

- A library/API behaved differently than the README or your assumption expected.
- A tax rate, format, or rule needed correcting against a real source.
- You chose an approach, hit a wall, and backtracked — record the wall.
- A test caught something subtle, or a property was harder to prove than it looked.
- You discovered a constraint that isn't written down anywhere else yet.

Don't log routine successes. Log the things that would make someone say *"oh, good to
know."*

## Format

Newest entries on top. Keep each one tight — a paragraph, not an essay. Link the commit
or file when useful.

```
## YYYY-MM-DD — short title
**Context:** what you were doing.
**Surprise:** what you expected vs. what actually happened.
**Resolution:** what you did about it.
**Takeaway:** the durable lesson for next time.
```

---

<!-- Add new lessons below this line, newest first. -->

## 2026-06-23 — Foundation docs created; no code lessons yet
**Context:** Bootstrapping the repo's agent-facing documentation before any code exists.
**Surprise:** None — this is the seed entry.
**Takeaway:** Every future agent: when something bites you, the lesson goes here, not just
in a commit message. The owner reads this file to learn what the codebase taught us.
