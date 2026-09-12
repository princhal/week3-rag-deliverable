---
name: explain-like-im-10
description: Explain a codebase, project, technical system, or complex concept in plain, playful language a 10-year-old (or total beginner) could follow, using an overarching analogy, a numbered "recipe" of steps, and everyday comparisons (candy bars, LEGO, filing cabinets) instead of jargon. Use this whenever the user asks to explain something "for a kid", "like I'm 5/10", "ELI5", "simply", "in plain English", "to a beginner", "non-technically", or similar — for a project, repo, script, architecture, or abstract concept (RAG, APIs, databases, algorithms, etc). Always ground the explanation in the real project by actually reading the relevant files first — never invent details about what the code does.
---

# Explain Like I'm 10

Turn a real, often complicated, technical thing into a short explanation a kid could actually follow — without dumbing down what it *does*, only how it's *said*.

## Why this works

A 10-year-old (or a total beginner) doesn't lack intelligence — they lack the shared vocabulary and mental models that make technical language efficient for experts. The fix isn't fewer ideas, it's swapping jargon for concepts the listener already owns: candy bars, LEGO, board games, secret codes, filing cabinets, matching games. Every technical concept has *some* everyday process that behaves the same way structurally — find that structural twin, not just a cute mascot.

This only works if it's true. Never sacrifice accuracy for cuteness — an explanation that's charming but wrong teaches the reader something false, which is worse than a confusing but correct one.

## Process

**1. Actually look at the real thing first.** Read the actual files, code, or docs before writing anything. Don't guess or generalize from the name of the project — a "RAG pipeline" could be doing wildly different things depending on the actual implementation. Use Read/Glob/Grep (or ask the user) to ground every claim in something you've verified. If you're explaining an abstract concept with no code (e.g. "explain how neural networks work"), it's fine to skip this step.

**2. Find one anchor analogy for the whole system.** Before breaking anything into steps, pick a single relatable role or scene that the *whole* project maps onto — a robot librarian, a lemonade stand, a relay race, a game of telephone. This becomes the thread the reader holds onto; every step below should feel like a scene inside that same story, not a new unrelated comparison each time.

**3. Break the process into numbered steps, like a recipe.** Most technical systems are a sequence (even if the real code branches or loops) — find the natural stages and number them. Steps should follow the *actual* order of operations in the real system, not an idealized or simplified one.

**4. For each step, give three things, tightly:**
   - A short emoji + punchy label (e.g. "✂️ Cut it into pieces")
   - The real technical name and, if explaining code, a pointer to the actual file/function so the explanation stays traceable to reality (e.g. "(`chunkers.py`)")
   - One concrete everyday analogy — something a kid has physically touched or played (candy bar, LEGO, matching game, secret decoder ring, filing cabinet). Bold the key analogy word so it's scannable.

   Keep each step to 1-3 sentences. Resist the urge to explain everything about a step — say only what's needed to keep the story moving.

**5. Close with "The big question it's answering."** Compress the entire system down to one plain-English question in quotes — this is the payoff that proves the reader actually understood the point, not just the mechanics. Example: *"If I cut up a book differently, does my robot get better or worse at finding the right answer?"*

**6. Optionally, name-drop the real term at the very end.** One line connecting the kid-friendly story back to the actual technical vocabulary (e.g. "This is a real technique called RAG — Retrieval-Augmented Generation") so the reader picks up the real word once they already have the concept for it. Skip this if the user already knows the term and just wants the concept explained simply.

## Style rules

- Keep it short and scannable — this is not a wall of text. If the real system has 6 steps, use 6 short entries, not 6 paragraphs.
- Use bold only for the analogy word itself, not whole sentences.
- Don't editorialize about how simple or clever the explanation is — just give it.
- Match tone to audience: playful and concrete for a literal 10-year-old; you can dial the whimsy down slightly (fewer emoji, slightly more vocabulary) for an adult beginner who asked for "plain English" rather than "for a kid" — but keep the analogy-driven structure either way.
- Never let an analogy contradict the real mechanics. If a metaphor would require lying about what the system does, find a different metaphor rather than bending the facts.

## Example skeleton

```
## What this project does

[One or two sentences with the anchor analogy for the whole system.]

## The steps (like a recipe)

1. **📖 [Punchy label]** (`real_file.py`) — [What it does] — like [everyday analogy].
2. **✂️ [Punchy label]** (`real_file.py`) — ...
   - [If a step has sub-variants, list them briefly the same way]
...

## The big question it's answering

**"[One plain-English question in quotes]"**

[Optional closing line naming the real technical term.]
```
