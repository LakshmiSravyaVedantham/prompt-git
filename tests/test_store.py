"""Tests for prompt_git.store module."""

from pathlib import Path

import pytest

from prompt_git.store import PromptStore


@pytest.fixture
def tmp_store(tmp_path: Path) -> PromptStore:
    """Create and initialize a fresh store in a temp directory."""
    store = PromptStore(tmp_path)
    store.init()
    return store


class TestInit:
    def test_init_creates_db_file(self, tmp_path: Path) -> None:
        store = PromptStore(tmp_path)
        store.init()
        db = tmp_path / ".prompt-git" / "store.db"
        assert db.exists(), "store.db should be created on init"

    def test_init_creates_store_dir(self, tmp_path: Path) -> None:
        store = PromptStore(tmp_path)
        store.init()
        assert (tmp_path / ".prompt-git").is_dir()

    def test_init_idempotent(self, tmp_path: Path) -> None:
        store = PromptStore(tmp_path)
        store.init()
        store.init()  # Second init should not raise
        assert (tmp_path / ".prompt-git" / "store.db").exists()


class TestAddAndCommit:
    def test_add_stages_prompt(self, tmp_store: PromptStore) -> None:
        tmp_store.add("summarize", "Summarize the following text:")
        staged = tmp_store.status()
        assert "summarize" in staged
        assert staged["summarize"] == "Summarize the following text:"

    def test_commit_stores_correctly(self, tmp_store: PromptStore) -> None:
        tmp_store.add("classify", "Classify the sentiment:")
        commits = tmp_store.commit("initial classify prompt")
        assert len(commits) == 1
        c = commits[0]
        assert c.prompt_name == "classify"
        assert c.content == "Classify the sentiment:"
        assert c.message == "initial classify prompt"
        assert c.id  # non-empty hash

    def test_commit_clears_staging_area(self, tmp_store: PromptStore) -> None:
        tmp_store.add("translate", "Translate to French:")
        tmp_store.commit("add translate")
        staged = tmp_store.status()
        assert staged == {}

    def test_commit_with_metadata(self, tmp_store: PromptStore) -> None:
        tmp_store.add("qa", "Answer the question:")
        commits = tmp_store.commit(
            "add QA prompt",
            model="claude-3-5-sonnet",
            temperature=0.7,
            notes="Works well on factual tasks",
        )
        c = commits[0]
        assert c.model == "claude-3-5-sonnet"
        assert c.temperature == 0.7
        assert c.notes == "Works well on factual tasks"

    def test_commit_nothing_raises(self, tmp_store: PromptStore) -> None:
        with pytest.raises(ValueError, match="Nothing staged"):
            tmp_store.commit("empty commit")

    def test_commit_sets_parent_id(self, tmp_store: PromptStore) -> None:
        tmp_store.add("summarize", "Version 1")
        first = tmp_store.commit("v1")[0]
        tmp_store.add("summarize", "Version 2")
        second = tmp_store.commit("v2")[0]
        assert second.parent_id == first.id

    def test_commit_multiple_prompts(self, tmp_store: PromptStore) -> None:
        tmp_store.add("summarize", "Summarize:")
        tmp_store.add("classify", "Classify:")
        commits = tmp_store.commit("batch commit")
        names = {c.prompt_name for c in commits}
        assert names == {"summarize", "classify"}


class TestLog:
    def test_log_returns_commits_in_reverse_order(self, tmp_store: PromptStore) -> None:
        tmp_store.add("p", "v1")
        tmp_store.commit("first")
        tmp_store.add("p", "v2")
        tmp_store.commit("second")
        tmp_store.add("p", "v3")
        tmp_store.commit("third")

        commits = tmp_store.log()
        messages = [c.message for c in commits]
        assert messages.index("third") < messages.index("second") < messages.index("first")

    def test_log_filter_by_prompt_name(self, tmp_store: PromptStore) -> None:
        tmp_store.add("foo", "foo content")
        tmp_store.add("bar", "bar content")
        tmp_store.commit("both")

        foo_logs = tmp_store.log(prompt_name="foo")
        assert all(c.prompt_name == "foo" for c in foo_logs)

    def test_log_respects_limit(self, tmp_store: PromptStore) -> None:
        for i in range(5):
            tmp_store.add("p", f"version {i}")
            tmp_store.commit(f"commit {i}")

        commits = tmp_store.log(limit=3)
        assert len(commits) == 3

    def test_log_empty_store(self, tmp_store: PromptStore) -> None:
        assert tmp_store.log() == []


class TestCheckout:
    def test_checkout_restores_content(self, tmp_store: PromptStore) -> None:
        tmp_store.add("summarize", "Original prompt")
        first = tmp_store.commit("original")[0]

        tmp_store.add("summarize", "Updated prompt")
        tmp_store.commit("updated")

        restored = tmp_store.checkout(first.id, "summarize")
        assert restored is not None
        assert restored.content == "Original prompt"

    def test_checkout_by_short_id(self, tmp_store: PromptStore) -> None:
        tmp_store.add("summarize", "Short ID test")
        c = tmp_store.commit("test")[0]
        short = c.id[:7]
        restored = tmp_store.checkout(short, "summarize")
        assert restored is not None
        assert restored.content == "Short ID test"

    def test_checkout_nonexistent_returns_none(self, tmp_store: PromptStore) -> None:
        result = tmp_store.checkout("deadbeef", "nonexistent")
        assert result is None


class TestTag:
    def test_tag_creates_and_retrieves(self, tmp_store: PromptStore) -> None:
        tmp_store.add("summarize", "Tagged prompt")
        c = tmp_store.commit("to be tagged")[0]

        tag = tmp_store.tag("v1.0", c.id, message="First release")
        assert tag.name == "v1.0"
        assert tag.commit_id == c.id
        assert tag.message == "First release"

    def test_get_tag(self, tmp_store: PromptStore) -> None:
        tmp_store.add("p", "content")
        c = tmp_store.commit("x")[0]
        tmp_store.tag("release", c.id)
        retrieved = tmp_store.get_tag("release")
        assert retrieved is not None
        assert retrieved.name == "release"
        assert retrieved.commit_id == c.id

    def test_get_commit_by_tag(self, tmp_store: PromptStore) -> None:
        tmp_store.add("summarize", "Tagged content")
        c = tmp_store.commit("tag target")[0]
        tmp_store.tag("stable", c.id)

        found = tmp_store.get_commit_by_tag("stable")
        assert found is not None
        assert found.id == c.id
        assert found.content == "Tagged content"

    def test_tag_nonexistent_commit_raises(self, tmp_store: PromptStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            tmp_store.tag("bad-tag", "deadbeef1234")

    def test_list_tags(self, tmp_store: PromptStore) -> None:
        tmp_store.add("p", "content")
        c = tmp_store.commit("x")[0]
        tmp_store.tag("alpha", c.id)
        tmp_store.tag("beta", c.id)
        tags = tmp_store.list_tags()
        names = {t.name for t in tags}
        assert {"alpha", "beta"}.issubset(names)


class TestFindStore:
    def test_find_store_from_subdir(self, tmp_path: Path) -> None:
        store = PromptStore(tmp_path)
        store.init()

        subdir = tmp_path / "subdir" / "deep"
        subdir.mkdir(parents=True)

        found = PromptStore.find_store(subdir)
        assert found is not None

    def test_find_store_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            PromptStore.find_store(tmp_path)
