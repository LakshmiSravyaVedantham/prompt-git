---
title: "I Built Git for LLM Prompts — Because `summarize_v3_FINAL_actually_final.txt` Isn't Working"
published: true
description: "prompt-git is a CLI tool that brings proper version control to your AI prompts. Track, diff, tag, and annotate prompt evolution — just like git, but for prompts."
tags: ai, llm, python, devtools, promptengineering
---

## The Problem Nobody Talks About

I track everything in git. My code. My configs. Even my dotfiles. But my AI prompts? They lived in a messy folder called `/prompts` with files like:

```
summarize.txt
summarize_v2.txt
summarize_better.txt
summarize_FINAL.txt
summarize_FINAL_v2.txt
summarize_v3_FINAL_actually_final.txt
```

Sound familiar?

The problem has a name: **prompt drift**. You tune a prompt obsessively until it works. You ship it. It works great. Then 3 months later, you want to roll back — and you have no idea what changed, when, or why. You don't know which version you actually used in production. You don't know what temperature you had it at when it stopped hallucinating.

Regular git helps a little, but it doesn't understand prompts. It can't track which model you were using, what temperature you tested at, or attach performance notes to a specific version.

So I built **prompt-git**.

---

## The Solution: 3-Line Demo

```bash
$ prompt-git init
$ prompt-git add summarize.txt
$ prompt-git commit -m "tighten output format" --model claude-3-5-sonnet --temp 0.3 --notes "BLEU score +12%"
```

That's it. Now you have a real version history for your prompts.

---

## What prompt-git Actually Does

```bash
# See your full prompt history in a beautiful table
$ prompt-git log

┌──────────┬────────────┬──────────────────────────┬─────────────────────┬──────┬────────────┬──────────────────┐
│ ID       │ Prompt     │ Message                  │ Model               │ Temp │ Tags       │ Timestamp        │
├──────────┼────────────┼──────────────────────────┼─────────────────────┼──────┼────────────┼──────────────────┤
│ b7d9e441 │ summarize  │ tighten output format    │ claude-3-5-sonnet   │ 0.3  │ v1.0       │ 2026-02-24 10:15 │
│ a3f8c12e │ summarize  │ initial summarize prompt │ claude-3-5-sonnet   │ 0.7  │            │ 2026-02-24 09:00 │
└──────────┴────────────┴──────────────────────────┴─────────────────────┴──────┴────────────┴──────────────────┘

# Diff two versions to see exactly what changed
$ prompt-git diff a3f8c12e b7d9e441

--- summarize@a3f8c12e
+++ summarize@b7d9e441
-Summarize the following text in 3 bullet points:
+Summarize the following text in 3 concise bullet points.
+Focus on key facts only. Do not include opinions or speculation.

+2 additions  -1 deletions

# Tag your best version
$ prompt-git tag v1.0 -m "Production-ready, BLEU +12%"

# Restore any version instantly
$ prompt-git checkout v1.0 --prompt summarize --write
```

---

## Architecture

The design is intentionally simple:

```
src/prompt_git/
├── cli.py      # Click commands + Rich terminal output
├── store.py    # SQLite backend (no external services)
├── diff.py     # Unified + word-level diff engine
└── models.py   # PromptCommit, PromptTag, PromptFile dataclasses
```

Everything lives in a `.prompt-git/store.db` SQLite file in your project directory. No API keys. No cloud. No dependencies beyond `click` and `rich`. It's just a fast local database that understands the shape of prompt version history.

Each `PromptCommit` stores:
- The full prompt text
- A SHA-1 content hash as its ID
- Parent commit ID (linked list of history)
- Optional: `model`, `temperature`, `notes`

This means you can track not just *what* changed, but *why* and *with what settings* — the context that git alone can't give you.

---

## What Makes This Different from Just Using Git?

You might be thinking: "Why not just commit your prompts to git?" 

You can! And you should. But `prompt-git` adds things that git doesn't know about:

| Feature | Regular git | prompt-git |
|---|---|---|
| Content diff | Yes | Yes |
| Commit messages | Yes | Yes |
| Tags / releases | Yes | Yes |
| LLM model metadata | No | Yes |
| Temperature tracking | No | Yes |
| Performance notes | No | Yes |
| Prompt-scoped history | No | Yes |
| Works without a git repo | No | Yes |
| Rich terminal UI | No | Yes |

The metadata is what makes it genuinely useful. When you see that `v1.0` used `temperature=0.3` and `claude-3-5-sonnet` and had a note saying "reduced hallucinations by 40%", you have actionable context — not just a diff.

---

## What I Learned Building This

**1. SQLite is wildly underrated for CLI tools.** A single `.db` file gives you transactions, queries, foreign keys, and WAL mode for free. No server, no config. It's the perfect backend for a local developer tool.

**2. Rich makes terminal UIs genuinely delightful.** The colored diff output, bordered panels, and formatted tables took maybe 30 minutes to add but make the tool feel professional. Never use `print()` in a CLI tool again.

**3. Click's `CliRunner` is incredibly good for testing.** I wrote the entire test suite using `CliRunner.isolated_filesystem()` — each test gets its own temp directory, no mocking required. The tests are fast, readable, and they catch real bugs.

**4. The hardest part wasn't the code — it was the UX.** What does `checkout` mean for a prompt? Should it write to a file? Should it just print to stdout? Getting those interaction patterns right took more thought than the SQLite schema.

---

## Install and Try It

```bash
pip install prompt-git
cd your-ai-project/
prompt-git init
prompt-git add your-prompt.txt
prompt-git commit -m "first tracked version"
prompt-git log
```

Full source: [github.com/LakshmiSravyaVedantham/prompt-git](https://github.com/LakshmiSravyaVedantham/prompt-git)

If you're building LLM applications and you're not tracking your prompts this way, your future self will thank you.

---

*Built with Python, Click, Rich, and SQLite. No AI APIs required — this is version control, not inference.*
