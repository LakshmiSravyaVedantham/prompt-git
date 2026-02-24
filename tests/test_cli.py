"""Tests for prompt_git CLI using Click's CliRunner."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from prompt_git.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def initialized_dir(runner: CliRunner, tmp_path: Path):
    """Provide a runner with an initialized prompt-git store directory."""
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0, result.output
        yield Path(td)


class TestInitCommand:
    def test_init_creates_prompt_git_directory(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert Path(".prompt-git").is_dir()
            assert Path(".prompt-git/store.db").exists()

    def test_init_output_message(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "Initialized" in result.output

    def test_init_already_initialized(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["init"])
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "Already initialized" in result.output


class TestAddCommand:
    def test_add_file(self, runner: CliRunner, initialized_dir: Path) -> None:
        prompt_file = initialized_dir / "summarize.txt"
        prompt_file.write_text("Summarize the following text concisely:")
        result = runner.invoke(main, ["add", str(prompt_file)])
        assert result.exit_code == 0
        assert "Staged" in result.output
        assert "summarize" in result.output

    def test_add_nonexistent_file(self, runner: CliRunner, initialized_dir: Path) -> None:
        result = runner.invoke(main, ["add", "nonexistent.txt"])
        assert result.exit_code != 0

    def test_add_without_init(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("myprompt.txt").write_text("content")
            result = runner.invoke(main, ["add", "myprompt.txt"])
            assert result.exit_code != 0


class TestCommitCommand:
    def test_commit_after_add(self, runner: CliRunner, initialized_dir: Path) -> None:
        prompt_file = initialized_dir / "classify.txt"
        prompt_file.write_text("Classify the sentiment as positive, negative, or neutral:")
        runner.invoke(main, ["add", str(prompt_file)])
        result = runner.invoke(main, ["commit", "-m", "initial classify prompt"])
        assert result.exit_code == 0
        assert "Committed" in result.output

    def test_commit_without_add(self, runner: CliRunner, initialized_dir: Path) -> None:
        result = runner.invoke(main, ["commit", "-m", "empty commit"])
        assert result.exit_code != 0

    def test_commit_with_model_and_temp(self, runner: CliRunner, initialized_dir: Path) -> None:
        prompt_file = initialized_dir / "qa.txt"
        prompt_file.write_text("Answer the question accurately:")
        runner.invoke(main, ["add", str(prompt_file)])
        result = runner.invoke(
            main,
            ["commit", "-m", "qa prompt", "--model", "claude-3-5-sonnet", "--temp", "0.5"],
        )
        assert result.exit_code == 0

    def test_commit_requires_message(self, runner: CliRunner, initialized_dir: Path) -> None:
        result = runner.invoke(main, ["commit"])
        assert result.exit_code != 0


class TestLogCommand:
    def _add_and_commit(
        self, runner: CliRunner, dirpath: Path, name: str, content: str, message: str
    ) -> None:
        f = dirpath / f"{name}.txt"
        f.write_text(content)
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", message])

    def test_log_shows_commits(self, runner: CliRunner, initialized_dir: Path) -> None:
        self._add_and_commit(runner, initialized_dir, "p", "content v1", "first commit")
        result = runner.invoke(main, ["log"])
        assert result.exit_code == 0
        assert "first commit" in result.output

    def test_log_empty_shows_message(self, runner: CliRunner, initialized_dir: Path) -> None:
        result = runner.invoke(main, ["log"])
        assert result.exit_code == 0
        assert "No commits" in result.output

    def test_log_with_limit(self, runner: CliRunner, initialized_dir: Path) -> None:
        for i in range(5):
            self._add_and_commit(runner, initialized_dir, f"p{i}", f"v{i}", f"commit {i}")
        result = runner.invoke(main, ["log", "--limit", "2"])
        assert result.exit_code == 0


class TestStatusCommand:
    def test_status_shows_staged(self, runner: CliRunner, initialized_dir: Path) -> None:
        f = initialized_dir / "status_test.txt"
        f.write_text("Hello prompt")
        runner.invoke(main, ["add", str(f)])
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "status_test" in result.output

    def test_status_empty(self, runner: CliRunner, initialized_dir: Path) -> None:
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0


class TestTagCommand:
    def test_tag_latest_commit(self, runner: CliRunner, initialized_dir: Path) -> None:
        f = initialized_dir / "prompt.txt"
        f.write_text("Tag me")
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", "to be tagged"])
        result = runner.invoke(main, ["tag", "v1.0"])
        assert result.exit_code == 0
        assert "v1.0" in result.output

    def test_tag_with_message(self, runner: CliRunner, initialized_dir: Path) -> None:
        f = initialized_dir / "prompt.txt"
        f.write_text("Tag me with message")
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", "tagged"])
        result = runner.invoke(main, ["tag", "release-1", "-m", "First stable release"])
        assert result.exit_code == 0

    def test_tag_no_commits_fails(self, runner: CliRunner, initialized_dir: Path) -> None:
        result = runner.invoke(main, ["tag", "v0"])
        assert result.exit_code != 0


class TestDiffCommand:
    def test_diff_two_versions(self, runner: CliRunner, initialized_dir: Path) -> None:
        f = initialized_dir / "evolving.txt"
        f.write_text("Version 1 of the prompt")
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", "v1"])

        f.write_text("Version 2 of the prompt with more detail")
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", "v2"])

        # Get commit IDs from log output via the store directly
        from prompt_git.store import PromptStore

        store = PromptStore.find_store(initialized_dir)
        logs = store.log()
        assert len(logs) >= 2
        result = runner.invoke(main, ["diff", logs[1].id, logs[0].id])
        assert result.exit_code == 0


class TestShowCommand:
    def test_show_commit(self, runner: CliRunner, initialized_dir: Path) -> None:
        f = initialized_dir / "showme.txt"
        f.write_text("Show me the details")
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", "show test", "--model", "gpt-4"])

        from prompt_git.store import PromptStore

        store = PromptStore.find_store(initialized_dir)
        logs = store.log()
        result = runner.invoke(main, ["show", logs[0].id])
        assert result.exit_code == 0
        assert "show test" in result.output
        assert "gpt-4" in result.output

    def test_show_nonexistent_fails(self, runner: CliRunner, initialized_dir: Path) -> None:
        result = runner.invoke(main, ["show", "deadbeef"])
        assert result.exit_code != 0


class TestCheckoutCommand:
    def test_checkout_restores_version(self, runner: CliRunner, initialized_dir: Path) -> None:
        f = initialized_dir / "checkout_test.txt"
        f.write_text("Original content")
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", "original"])

        f.write_text("Updated content")
        runner.invoke(main, ["add", str(f)])
        runner.invoke(main, ["commit", "-m", "updated"])

        from prompt_git.store import PromptStore

        store = PromptStore.find_store(initialized_dir)
        logs = store.log()
        original_commit = logs[-1]  # oldest

        result = runner.invoke(main, ["checkout", original_commit.id, "--prompt", "checkout_test"])
        assert result.exit_code == 0
        assert "Checked out" in result.output
