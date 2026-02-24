"""Diff utilities for prompt-git: unified diff and word-level diff."""

import difflib
from typing import List, Tuple


def unified_diff(
    old_content: str,
    new_content: str,
    old_label: str = "old",
    new_label: str = "new",
    context: int = 3,
) -> List[str]:
    """
    Return a list of rich-markup lines representing a unified diff.

    Added lines are styled green, removed lines red, headers cyan.
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_label,
            tofile=new_label,
            n=context,
        )
    )

    if not diff_lines:
        return []

    styled: List[str] = []
    for line in diff_lines:
        # Strip trailing newline for display
        display = line.rstrip("\n")
        if line.startswith("+++") or line.startswith("---"):
            styled.append(f"[bold cyan]{display}[/bold cyan]")
        elif line.startswith("@@"):
            styled.append(f"[cyan]{display}[/cyan]")
        elif line.startswith("+"):
            styled.append(f"[green]{display}[/green]")
        elif line.startswith("-"):
            styled.append(f"[red]{display}[/red]")
        else:
            styled.append(display)
    return styled


def word_diff(old: str, new: str) -> str:
    """
    Inline word-level diff. Returns a single rich-markup string.

    Words added are shown in green, removed in red.
    """
    old_words = old.split()
    new_words = new.split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    parts: List[str] = []

    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            parts.append(" ".join(old_words[i1:i2]))
        elif opcode == "insert":
            parts.append(f"[green]{' '.join(new_words[j1:j2])}[/green]")
        elif opcode == "delete":
            parts.append(f"[red]{' '.join(old_words[i1:i2])}[/red]")
        elif opcode == "replace":
            parts.append(f"[red]{' '.join(old_words[i1:i2])}[/red]")
            parts.append(f"[green]{' '.join(new_words[j1:j2])}[/green]")

    return " ".join(parts)


def has_changes(old_content: str, new_content: str) -> bool:
    """Return True if the two contents differ."""
    return old_content != new_content


def count_changes(old_content: str, new_content: str) -> Tuple[int, int]:
    """Return (additions, deletions) line counts."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines))
    additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    return additions, deletions
