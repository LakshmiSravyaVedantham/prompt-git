"""Tests for prompt_git.diff module."""

from prompt_git.diff import count_changes, has_changes, unified_diff, word_diff


class TestUnifiedDiff:
    def test_unified_diff_detects_additions(self) -> None:
        old = "Hello world"
        new = "Hello world\nNew line added"
        lines = unified_diff(old, new, "old", "new")
        assert any("+" in line and "New line added" in line for line in lines)

    def test_unified_diff_detects_removals(self) -> None:
        old = "Hello world\nRemove this line"
        new = "Hello world"
        lines = unified_diff(old, new, "old", "new")
        assert any("-" in line and "Remove this line" in line for line in lines)

    def test_unified_diff_identical_returns_empty(self) -> None:
        content = "This is a prompt with no changes."
        lines = unified_diff(content, content)
        assert lines == []

    def test_unified_diff_has_headers(self) -> None:
        old = "line 1\nline 2"
        new = "line 1\nline 3"
        lines = unified_diff(old, new, "a/prompt", "b/prompt")
        header_lines = [ln for ln in lines if "a/prompt" in ln or "b/prompt" in ln]
        assert len(header_lines) >= 2

    def test_unified_diff_styled_additions_green(self) -> None:
        old = "before"
        new = "before\nafter"
        lines = unified_diff(old, new)
        green_lines = [ln for ln in lines if "[green]" in ln]
        assert len(green_lines) > 0

    def test_unified_diff_styled_removals_red(self) -> None:
        old = "before\nremoved"
        new = "before"
        lines = unified_diff(old, new)
        red_lines = [ln for ln in lines if "[red]" in ln]
        assert len(red_lines) > 0

    def test_unified_diff_empty_to_content(self) -> None:
        old = ""
        new = "Brand new prompt"
        lines = unified_diff(old, new)
        assert len(lines) > 0

    def test_unified_diff_content_to_empty(self) -> None:
        old = "Existing prompt"
        new = ""
        lines = unified_diff(old, new)
        assert len(lines) > 0


class TestWordDiff:
    def test_word_diff_highlights_added_words(self) -> None:
        old = "Summarize the text"
        new = "Summarize the long text carefully"
        result = word_diff(old, new)
        assert "[green]" in result

    def test_word_diff_highlights_removed_words(self) -> None:
        old = "Summarize the long text carefully"
        new = "Summarize the text"
        result = word_diff(old, new)
        assert "[red]" in result

    def test_word_diff_no_change(self) -> None:
        content = "No changes here"
        result = word_diff(content, content)
        assert "[green]" not in result
        assert "[red]" not in result
        assert "No changes here" in result

    def test_word_diff_complete_replacement(self) -> None:
        old = "old prompt text"
        new = "new prompt text"
        result = word_diff(old, new)
        assert "[red]old[/red]" in result
        assert "[green]new[/green]" in result


class TestHasChanges:
    def test_has_changes_same_content(self) -> None:
        assert not has_changes("same", "same")

    def test_has_changes_different_content(self) -> None:
        assert has_changes("old", "new")

    def test_has_changes_empty_strings(self) -> None:
        assert not has_changes("", "")

    def test_has_changes_whitespace_differs(self) -> None:
        assert has_changes("a b", "a  b")


class TestCountChanges:
    def test_count_additions(self) -> None:
        # Adding 2 new lines to an existing line: unified diff replaces old line
        # with all 3 new lines, so additions >= 2
        old = "line 1"
        new = "line 1\nline 2\nline 3"
        adds, dels = count_changes(old, new)
        assert adds >= 2  # at minimum 2 new lines introduced
        assert dels >= 0

    def test_count_deletions(self) -> None:
        # Removing 2 lines from 3: unified diff replaces old 3 lines
        # with new 1 line, so deletions >= 2
        old = "line 1\nline 2\nline 3"
        new = "line 1"
        adds, dels = count_changes(old, new)
        assert dels >= 2  # at minimum 2 lines removed
        assert adds >= 0

    def test_count_no_changes(self) -> None:
        content = "unchanged"
        adds, dels = count_changes(content, content)
        assert adds == 0
        assert dels == 0

    def test_count_mixed_changes(self) -> None:
        old = "keep\nremove this"
        new = "keep\nadd this"
        adds, dels = count_changes(old, new)
        assert adds >= 1
        assert dels >= 1

    def test_count_pure_additions(self) -> None:
        # Use newline-terminated lines so unified_diff sees a clean append
        old = "first line\nsecond line\n"
        new = "first line\nsecond line\nthird line\n"
        adds, dels = count_changes(old, new)
        assert adds == 1
        assert dels == 0

    def test_count_pure_deletions(self) -> None:
        # Use newline-terminated lines so unified_diff sees a clean removal
        old = "first line\nsecond line\nthird line\n"
        new = "first line\nsecond line\n"
        adds, dels = count_changes(old, new)
        assert adds == 0
        assert dels == 1
