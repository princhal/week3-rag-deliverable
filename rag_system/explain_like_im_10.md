# RAG System — Explained Simply

> A plain-English explanation of what this project does, written for anyone
> who has never heard of RAG, embeddings, or vector databases.

---

## What this project does

Imagine you have a really thick book and a robot helper who answers questions about it. Before the robot can help, someone has to tear the book into small cards and teach the robot what each card "feels like." This project tests three different ways of tearing the book — and figures out which way makes the robot best at finding the right card when you ask a question.

---

## The steps (like a recipe)

1. **📖 Read the book** (`extract.py`) — Opens the PDF page by page and pulls out all the text — like photocopying every page of a **library book**.

2. **🧹 Clean it up** (`clean.py`) — Removes page numbers, headers, and weird symbols — like erasing all the **sticky notes** someone left in the margins.

3. **✂️ Cut it three ways** (`chunk.py`) — Splits the text into small pieces using three different scissors:
   - *Equal slices* — every piece is exactly 512 words, like cutting a **candy bar** into equal squares
   - *Natural breaks* — cuts at paragraphs, like tearing a **newspaper** at the article edges
   - *Sentence windows* — grabs 5 sentences at a time, sliding forward 2, like a **magnifying glass** moving slowly across a page

4. **🔢 Give each piece a secret number** (`embed.py`) — Sends every piece to OpenAI, which turns it into a list of 1,536 numbers that captures its meaning — like giving each card a **fingerprint**.

5. **🗄️ File them away** (`embed.py` → Supabase) — Stores all the fingerprints in a database with a special index so lookups are fast — like a **filing cabinet** that can find the closest match in milliseconds.

6. **🔍 Ask 10 questions** (`query.py`) — Each question gets its own fingerprint too, then the database finds the 5 cards whose fingerprints are most similar — like a **matching game**.

7. **🏆 Score the results** (`evaluate.py`) — Checks whether the right card showed up in the top 3 answers — and crowns the winning cutting method.

---

## The big question it's answering

> **"If you slice a book differently, does your robot get better or worse at finding the right answer?"**

---

## The three cutting methods, side by side

| Method | How it cuts | Real name | Best for |
|---|---|---|---|
| Equal slices | Every piece = 512 words exactly | Fixed-size chunking | Precise single facts |
| Natural breaks | Cuts at paragraphs and sentences | Structural chunking | Section-level questions |
| Sliding window | 5 sentences, moves 2 at a time | Semantic windowing | Step-by-step and multi-sentence answers |

---

## How we decide the winner

For each of the 10 questions, we check: did the robot find the right card in its top 3 guesses?
- **Yes** → score 1
- **No** → score 0

Add up the scores across all 10 questions for each cutting method. The highest score wins.

---

## The real technical name

This is a real technique called **RAG — Retrieval-Augmented Generation**. It's how AI assistants look things up in documents instead of guessing from memory.

---

*Generated using the `explain-like-im-10` skill.*
