"""SQLite-backed storage engine for prompt-git."""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from prompt_git.models import PromptCommit, PromptFile, PromptTag

STORE_DIR = ".prompt-git"
STORE_FILE = "store.db"


class PromptStore:
    """SQLite-backed store for prompt commits, files, and tags."""

    def __init__(self, path: Path):
        self.store_dir = path / STORE_DIR
        self.db_path = self.store_dir / STORE_FILE
        self._staged: Dict[str, str] = {}  # prompt_name -> content
        self._conn: Optional[sqlite3.Connection] = None

    @classmethod
    def find_store(cls, start: Optional[Path] = None) -> "PromptStore":
        """Walk up directories to find a .prompt-git store."""
        current = Path(start or Path.cwd()).resolve()
        while True:
            candidate = current / STORE_DIR / STORE_FILE
            if candidate.exists():
                store = cls(current)
                store._connect()
                return store
            parent = current.parent
            if parent == current:
                raise FileNotFoundError("No prompt-git store found. Run 'prompt-git init' first.")
            current = parent

    def _connect(self) -> None:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row

    def _cursor(self) -> sqlite3.Cursor:
        if self._conn is None:
            self._connect()
        assert self._conn is not None
        return self._conn.cursor()

    def init(self) -> None:
        """Initialize the store: create directory and tables."""
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._connect()
        cur = self._cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS commits (
                id TEXT PRIMARY KEY,
                prompt_name TEXT NOT NULL,
                content TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                parent_id TEXT,
                model TEXT,
                temperature REAL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS tags (
                name TEXT PRIMARY KEY,
                commit_id TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (commit_id) REFERENCES commits(id)
            );

            CREATE TABLE IF NOT EXISTS files (
                name TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                current_commit_id TEXT,
                FOREIGN KEY (current_commit_id) REFERENCES commits(id)
            );

            CREATE TABLE IF NOT EXISTS staged (
                prompt_name TEXT PRIMARY KEY,
                content TEXT NOT NULL
            );
            """)
        assert self._conn is not None
        self._conn.commit()

    def _load_staged(self) -> Dict[str, str]:
        cur = self._cursor()
        cur.execute("SELECT prompt_name, content FROM staged")
        return {row["prompt_name"]: row["content"] for row in cur.fetchall()}

    def _save_staged(self, staged: Dict[str, str]) -> None:
        cur = self._cursor()
        cur.execute("DELETE FROM staged")
        for name, content in staged.items():
            cur.execute(
                "INSERT INTO staged (prompt_name, content) VALUES (?, ?)",
                (name, content),
            )
        assert self._conn is not None
        self._conn.commit()

    def _make_commit_id(self, prompt_name: str, content: str, ts: str) -> str:
        raw = f"{prompt_name}:{content}:{ts}"
        return hashlib.sha1(raw.encode()).hexdigest()

    def add(self, prompt_name: str, content: str) -> None:
        """Stage a prompt for the next commit."""
        staged = self._load_staged()
        staged[prompt_name] = content
        self._save_staged(staged)

    def commit(
        self,
        message: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> List[PromptCommit]:
        """Commit all staged prompts. Returns list of new PromptCommit objects."""
        staged = self._load_staged()
        if not staged:
            raise ValueError("Nothing staged. Use 'prompt-git add' first.")

        committed = []
        ts = datetime.utcnow().isoformat()
        cur = self._cursor()

        for prompt_name, content in staged.items():
            commit_id = self._make_commit_id(prompt_name, content, ts)

            # Find parent
            cur.execute(
                "SELECT id FROM commits WHERE prompt_name = ? ORDER BY timestamp DESC LIMIT 1",
                (prompt_name,),
            )
            row = cur.fetchone()
            parent_id = row["id"] if row else None

            cur.execute(
                """INSERT OR IGNORE INTO commits
                   (id, prompt_name, content, message, timestamp,
                    parent_id, model, temperature, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    commit_id,
                    prompt_name,
                    content,
                    message,
                    ts,
                    parent_id,
                    model,
                    temperature,
                    notes,
                ),
            )

            # Upsert file record
            cur.execute(
                """INSERT INTO files (name, path, current_commit_id) VALUES (?, ?, ?)
                   ON CONFLICT(name) DO UPDATE
                   SET current_commit_id = excluded.current_commit_id""",
                (prompt_name, f"{prompt_name}.txt", commit_id),
            )

            committed.append(
                PromptCommit(
                    id=commit_id,
                    prompt_name=prompt_name,
                    content=content,
                    message=message,
                    timestamp=datetime.fromisoformat(ts),
                    parent_id=parent_id,
                    model=model,
                    temperature=temperature,
                    notes=notes,
                )
            )

        assert self._conn is not None
        self._conn.commit()
        self._save_staged({})
        return committed

    def log(self, prompt_name: Optional[str] = None, limit: int = 10) -> List[PromptCommit]:
        """Return commits in reverse chronological order."""
        cur = self._cursor()
        if prompt_name:
            cur.execute(
                """SELECT c.*, GROUP_CONCAT(t.name) as tag_names
                   FROM commits c
                   LEFT JOIN tags t ON t.commit_id = c.id
                   WHERE c.prompt_name = ?
                   GROUP BY c.id
                   ORDER BY c.timestamp DESC
                   LIMIT ?""",
                (prompt_name, limit),
            )
        else:
            cur.execute(
                """SELECT c.*, GROUP_CONCAT(t.name) as tag_names
                   FROM commits c
                   LEFT JOIN tags t ON t.commit_id = c.id
                   GROUP BY c.id
                   ORDER BY c.timestamp DESC
                   LIMIT ?""",
                (limit,),
            )
        rows = cur.fetchall()
        return [self._row_to_commit(row) for row in rows]

    def _row_to_commit(self, row: sqlite3.Row) -> PromptCommit:
        tags = []
        tag_names = row["tag_names"]
        if tag_names:
            tags = tag_names.split(",")
        return PromptCommit(
            id=row["id"],
            prompt_name=row["prompt_name"],
            content=row["content"],
            message=row["message"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            parent_id=row["parent_id"],
            model=row["model"],
            temperature=row["temperature"],
            tags=tags,
            notes=row["notes"],
        )

    def get_commit(self, commit_id: str) -> Optional[PromptCommit]:
        """Retrieve a single commit by full or short ID."""
        cur = self._cursor()
        # Try exact match first
        cur.execute(
            """SELECT c.*, GROUP_CONCAT(t.name) as tag_names
               FROM commits c
               LEFT JOIN tags t ON t.commit_id = c.id
               WHERE c.id = ?
               GROUP BY c.id""",
            (commit_id,),
        )
        row = cur.fetchone()
        if row:
            return self._row_to_commit(row)
        # Try prefix match
        cur.execute(
            """SELECT c.*, GROUP_CONCAT(t.name) as tag_names
               FROM commits c
               LEFT JOIN tags t ON t.commit_id = c.id
               WHERE c.id LIKE ?
               GROUP BY c.id
               LIMIT 1""",
            (f"{commit_id}%",),
        )
        row = cur.fetchone()
        return self._row_to_commit(row) if row else None

    def get_commit_by_tag(self, tag_name: str) -> Optional[PromptCommit]:
        """Retrieve a commit by tag name."""
        cur = self._cursor()
        cur.execute("SELECT commit_id FROM tags WHERE name = ?", (tag_name,))
        row = cur.fetchone()
        if not row:
            return None
        return self.get_commit(row["commit_id"])

    def diff(self, commit_a_id: str, commit_b_id: str, prompt_name: Optional[str] = None):
        """Return (commit_a, commit_b) for diffing. Resolves tags and short IDs."""
        a = self.get_commit(commit_a_id) or self.get_commit_by_tag(commit_a_id)
        b = self.get_commit(commit_b_id) or self.get_commit_by_tag(commit_b_id)
        return a, b

    def checkout(self, ref: str, prompt_name: str) -> Optional[PromptCommit]:
        """Restore a prompt to a given commit or tag."""
        commit = self.get_commit(ref) or self.get_commit_by_tag(ref)
        if not commit:
            return None
        if prompt_name and commit.prompt_name != prompt_name:
            # Find commit for this prompt at the given ref timestamp
            return None
        # Update file record
        cur = self._cursor()
        cur.execute(
            """INSERT INTO files (name, path, current_commit_id) VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET current_commit_id = excluded.current_commit_id""",
            (commit.prompt_name, f"{commit.prompt_name}.txt", commit.id),
        )
        assert self._conn is not None
        self._conn.commit()
        return commit

    def tag(self, name: str, commit_id: str, message: Optional[str] = None) -> PromptTag:
        """Create a tag pointing to a commit."""
        commit = self.get_commit(commit_id)
        if not commit:
            raise ValueError(f"Commit '{commit_id}' not found.")
        ts = datetime.utcnow().isoformat()
        cur = self._cursor()
        cur.execute(
            "INSERT OR REPLACE INTO tags"
            " (name, commit_id, message, created_at) VALUES (?, ?, ?, ?)",
            (name, commit.id, message, ts),
        )
        assert self._conn is not None
        self._conn.commit()
        return PromptTag(
            name=name, commit_id=commit.id, message=message, created_at=datetime.fromisoformat(ts)
        )

    def get_tag(self, name: str) -> Optional[PromptTag]:
        cur = self._cursor()
        cur.execute("SELECT * FROM tags WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            return None
        return PromptTag(
            name=row["name"],
            commit_id=row["commit_id"],
            message=row["message"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_tags(self) -> List[PromptTag]:
        cur = self._cursor()
        cur.execute("SELECT * FROM tags ORDER BY created_at DESC")
        rows = cur.fetchall()
        return [
            PromptTag(
                name=row["name"],
                commit_id=row["commit_id"],
                message=row["message"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def status(self) -> Dict[str, str]:
        """Return currently staged prompts as {name: content}."""
        return self._load_staged()

    def get_file(self, prompt_name: str) -> Optional[PromptFile]:
        cur = self._cursor()
        cur.execute("SELECT * FROM files WHERE name = ?", (prompt_name,))
        row = cur.fetchone()
        if not row:
            return None
        return PromptFile(
            name=row["name"],
            path=row["path"],
            current_commit_id=row["current_commit_id"],
        )

    def list_files(self) -> List[PromptFile]:
        cur = self._cursor()
        cur.execute("SELECT * FROM files")
        rows = cur.fetchall()
        return [
            PromptFile(
                name=row["name"], path=row["path"], current_commit_id=row["current_commit_id"]
            )
            for row in rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
