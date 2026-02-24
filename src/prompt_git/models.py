"""Data models for prompt-git: PromptCommit, PromptTag, PromptFile."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class PromptCommit:
    """Represents a committed version of a prompt."""

    id: str  # SHA-like hash of content+timestamp
    prompt_name: str  # e.g. "summarize", "classify"
    content: str  # full prompt text
    message: str  # commit message
    timestamp: datetime
    parent_id: Optional[str] = None
    model: Optional[str] = None  # e.g. "claude-3-5-sonnet"
    temperature: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None  # performance notes


@dataclass
class PromptTag:
    """Represents a named tag pointing to a commit."""

    name: str
    commit_id: str
    message: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class PromptFile:
    """Represents a tracked prompt file."""

    name: str
    path: str
    current_commit_id: Optional[str] = None
