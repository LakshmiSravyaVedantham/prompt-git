# prompt-git

> **Version control for LLM prompts. Because `summarize_v3_FINAL_actually_final.txt` is not a version control strategy.**

[![CI](https://github.com/LakshmiSravyaVedantham/prompt-git/actions/workflows/ci.yml/badge.svg)](https://github.com/LakshmiSravyaVedantham/prompt-git/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`prompt-git` brings git-style version control to your LLM prompt files. Track how your prompts evolve, diff versions, tag releases, and annotate with performance metadata — all from the CLI.

---

## Why?

You spend hours tuning a prompt. It works beautifully. Three months later, you have 14 files named:

```
summarize.txt
summarize_v2.txt
summarize_better.txt
summarize_FINAL.txt
summarize_FINAL_v2.txt
summarize_v3_FINAL_actually_final.txt
```

And you have no idea what changed between them or which one scored best.

`prompt-git` solves this by treating prompts as first-class artifacts with proper version history, diffs, tags, and metadata (model, temperature, performance notes).

---

## Demo

```
$ prompt-git init
Initialized empty prompt-git store
Location: /my-project/.prompt-git

$ echo "Summarize the following text in 3 bullet points:" > summarize.txt
$ prompt-git add summarize.txt
Staged prompt 'summarize'

$ prompt-git commit -m "initial summarize prompt" --model claude-3-5-sonnet --temp 0.7
Committed [a3f8c12e] summarize: initial summarize prompt

$ prompt-git log
┌─────────────────────────────────────────────────────────────────────────┐
│                       Prompt Commit History                             │
├──────────┬────────────┬──────────────────────┬──────────────────────────┤
│ ID       │ Prompt     │ Message              │ Timestamp                │
├──────────┼────────────┼──────────────────────┼──────────────────────────┤
│ a3f8c12e │ summarize  │ initial summarize... │ 2026-02-24 10:00         │
└──────────┴────────────┴──────────────────────┴──────────────────────────┘

$ prompt-git diff a3f8c12e b7d9e441
--- summarize@a3f8c12e
+++ summarize@b7d9e441
-Summarize the following text in 3 bullet points:
+Summarize the following text in 3 concise bullet points.
+Focus on the most important facts only.

+2 additions  -1 deletions
```

---

## Install

```bash
pip install prompt-git
```

Or install from source:

```bash
git clone https://github.com/LakshmiSravyaVedantham/prompt-git.git
cd prompt-git
pip install -e ".[dev]"
```

---

## Quick Start

```bash
# 1. Initialize in your project directory
cd my-ai-project/
prompt-git init

# 2. Write your prompt
echo "Classify the sentiment as positive, negative, or neutral." > classify.txt

# 3. Stage and commit
prompt-git add classify.txt
prompt-git commit -m "initial sentiment classifier" --model gpt-4 --temp 0.0

# 4. Iterate and track changes
echo "Classify the sentiment. Output ONLY one word: positive, negative, or neutral." > classify.txt
prompt-git add classify.txt
prompt-git commit -m "force single-word output" --notes "reduces hallucination by 40%"

# 5. See history
prompt-git log

# 6. Diff two versions
prompt-git diff <commit1> <commit2>

# 7. Tag a working version
prompt-git tag v1.0 -m "Production-ready classifier"

# 8. Restore an old version
prompt-git checkout v1.0 --prompt classify --write
```

---

## Command Reference

| Command | Description |
|---|---|
| `prompt-git init` | Initialize a store in the current directory |
| `prompt-git add <file>` | Stage a prompt file for the next commit |
| `prompt-git commit -m "msg"` | Commit staged prompts |
| `prompt-git log` | Show commit history (colorized table) |
| `prompt-git diff <id1> <id2>` | Show unified diff between two versions |
| `prompt-git checkout <ref> --prompt <name>` | Restore a prompt to a specific version |
| `prompt-git tag <name> [commit]` | Tag a commit with a name |
| `prompt-git status` | Show staged and tracked prompts |
| `prompt-git show <commit>` | Show full commit details |

### `commit` options

```
-m, --message TEXT     Commit message (required)
--model TEXT           LLM model used (e.g. claude-3-5-sonnet, gpt-4)
--temp FLOAT           Temperature setting
--notes TEXT           Performance notes for this version
```

### `diff` options

```
--word                 Use inline word-level diff instead of line diff
```

### `checkout` options

```
--prompt TEXT          Prompt name to restore (required)
--write                Write restored content to <prompt>.txt in current directory
```

---

## Storage

`prompt-git` stores all data in a SQLite database at `.prompt-git/store.db` relative to your project root. No external services, no API keys, no cloud — it's all local.

The store supports:
- Full commit history with parent chain
- Commit metadata (model, temperature, performance notes)
- Named tags pointing to any commit
- Staged area for pre-commit review

---

## Architecture

```
src/prompt_git/
├── __init__.py      # Public API exports
├── cli.py           # Click CLI commands with Rich output
├── store.py         # SQLite storage engine
├── diff.py          # Unified + word-level diff utilities
└── models.py        # PromptCommit, PromptTag, PromptFile dataclasses
```

---

## Development

```bash
git clone https://github.com/LakshmiSravyaVedantham/prompt-git.git
cd prompt-git
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -v

# Format and lint
black src/ tests/
isort src/ tests/
flake8 src/ tests/ --max-line-length 100
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
