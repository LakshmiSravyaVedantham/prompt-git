"""Click CLI for prompt-git: init, add, commit, log, diff, checkout, tag, status, show."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prompt_git.diff import count_changes, unified_diff, word_diff
from prompt_git.store import PromptStore

console = Console()
err_console = Console(stderr=True)


def _get_store() -> PromptStore:
    """Find and return the nearest prompt-git store."""
    try:
        return PromptStore.find_store()
    except FileNotFoundError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


def _short_id(commit_id: str, length: int = 8) -> str:
    return commit_id[:length]


@click.group()
@click.version_option("0.1.0", prog_name="prompt-git")
def main() -> None:
    """prompt-git: Version control for LLM prompts."""
    pass


@main.command()
def init() -> None:
    """Initialize a prompt-git store in the current directory."""
    cwd = Path.cwd()
    store = PromptStore(cwd)
    store_dir = cwd / ".prompt-git"
    if store_dir.exists():
        console.print("[yellow]Already initialized.[/yellow] Store exists at .prompt-git/")
        return
    store.init()
    console.print(
        Panel(
            "[green]Initialized empty prompt-git store[/green]\n"
            f"Location: [bold]{store_dir}[/bold]",
            title="prompt-git init",
            border_style="green",
        )
    )


@main.command()
@click.argument("source")
def add(source: str) -> None:
    """Stage a prompt file or named prompt for tracking.

    SOURCE can be a file path (e.g. prompts/summarize.txt) or a prompt name.
    """
    store = _get_store()
    path = Path(source)

    if path.exists() and path.is_file():
        prompt_name = path.stem
        content = path.read_text(encoding="utf-8")
    else:
        # Treat as prompt name; look for <name>.txt in cwd
        txt_path = Path.cwd() / f"{source}.txt"
        if txt_path.exists():
            prompt_name = source
            content = txt_path.read_text(encoding="utf-8")
        else:
            err_console.print(
                f"[red]Error:[/red] '{source}' is not a file and no '{source}.txt' found."
            )
            sys.exit(1)

    store.add(prompt_name, content)
    console.print(f"[green]Staged[/green] prompt '[bold]{prompt_name}[/bold]'")


@main.command()
@click.option("-m", "--message", required=True, help="Commit message")
@click.option("--model", default=None, help="LLM model used (e.g. claude-3-5-sonnet)")
@click.option("--temp", "temperature", default=None, type=float, help="Temperature setting")
@click.option("--notes", default=None, help="Performance notes for this version")
def commit(
    message: str, model: Optional[str], temperature: Optional[float], notes: Optional[str]
) -> None:
    """Commit staged prompts with a message."""
    store = _get_store()
    try:
        commits = store.commit(message=message, model=model, temperature=temperature, notes=notes)
    except ValueError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    for c in commits:
        console.print(
            f"[green]Committed[/green] [{_short_id(c.id)}] "
            f"[bold]{c.prompt_name}[/bold]: {c.message}"
        )
        if c.model:
            console.print(f"  model: [cyan]{c.model}[/cyan]", end="")
            if c.temperature is not None:
                console.print(f"  temp: [cyan]{c.temperature}[/cyan]", end="")
            console.print()


@main.command()
@click.option("--prompt", "prompt_name", default=None, help="Filter by prompt name")
@click.option("--limit", default=10, show_default=True, help="Number of commits to show")
def log(prompt_name: Optional[str], limit: int) -> None:
    """Show commit history."""
    store = _get_store()
    commits = store.log(prompt_name=prompt_name, limit=limit)

    if not commits:
        console.print("[yellow]No commits yet.[/yellow]")
        return

    table = Table(
        title="Prompt Commit History",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        show_lines=True,
    )
    table.add_column("ID", style="yellow", no_wrap=True, width=10)
    table.add_column("Prompt", style="bold cyan", width=16)
    table.add_column("Message", width=30)
    table.add_column("Model", style="blue", width=16)
    table.add_column("Temp", width=6)
    table.add_column("Tags", style="green", width=14)
    table.add_column("Timestamp", style="dim", width=20)

    for c in commits:
        tag_str = ", ".join(c.tags) if c.tags else ""
        model_str = c.model or ""
        temp_str = str(c.temperature) if c.temperature is not None else ""
        ts_str = c.timestamp.strftime("%Y-%m-%d %H:%M")
        table.add_row(
            _short_id(c.id),
            c.prompt_name,
            c.message,
            model_str,
            temp_str,
            tag_str,
            ts_str,
        )

    console.print(table)


@main.command()
@click.argument("commit1")
@click.argument("commit2")
@click.option("--prompt", "prompt_name", default=None, help="Prompt name filter")
@click.option("--word", is_flag=True, default=False, help="Use inline word-level diff")
def diff(commit1: str, commit2: str, prompt_name: Optional[str], word: bool) -> None:
    """Show diff between two commits or tags."""
    store = _get_store()
    a, b = store.diff(commit1, commit2, prompt_name)

    if not a:
        err_console.print(f"[red]Error:[/red] Commit '{commit1}' not found.")
        sys.exit(1)
    if not b:
        err_console.print(f"[red]Error:[/red] Commit '{commit2}' not found.")
        sys.exit(1)

    old_label = f"{a.prompt_name}@{_short_id(a.id)}"
    new_label = f"{b.prompt_name}@{_short_id(b.id)}"

    console.print(
        Panel(
            f"[yellow]{old_label}[/yellow]  ->  [green]{new_label}[/green]",
            title="prompt-git diff",
            border_style="cyan",
        )
    )

    if word:
        result = word_diff(a.content, b.content)
        console.print(result)
    else:
        lines = unified_diff(a.content, b.content, old_label, new_label)
        if not lines:
            console.print("[dim]No differences.[/dim]")
        else:
            for line in lines:
                console.print(line, highlight=False)

    adds, dels = count_changes(a.content, b.content)
    console.print(f"\n[green]+{adds}[/green] additions  [red]-{dels}[/red] deletions")


@main.command()
@click.argument("ref")
@click.option("--prompt", "prompt_name", required=True, help="Prompt name to restore")
@click.option(
    "--write",
    is_flag=True,
    default=False,
    help="Write restored content to <prompt>.txt in current directory",
)
def checkout(ref: str, prompt_name: str, write: bool) -> None:
    """Restore a prompt to a specific commit or tag."""
    store = _get_store()
    commit = store.checkout(ref, prompt_name)

    if not commit:
        err_console.print(f"[red]Error:[/red] Could not find '{ref}' for prompt '{prompt_name}'.")
        sys.exit(1)

    console.print(
        Panel(
            f"[green]Checked out[/green] [bold]{commit.prompt_name}[/bold] "
            f"@ [{_short_id(commit.id)}]\n\n"
            f"[dim]{commit.message}[/dim]",
            title="prompt-git checkout",
            border_style="green",
        )
    )

    if write:
        out_path = Path.cwd() / f"{commit.prompt_name}.txt"
        out_path.write_text(commit.content, encoding="utf-8")
        console.print(f"[green]Written[/green] to [bold]{out_path}[/bold]")
    else:
        console.print("\n[bold]Content:[/bold]")
        console.print(commit.content)


@main.command()
@click.argument("name")
@click.argument("commit_ref", required=False, default=None)
@click.option("-m", "--message", default=None, help="Tag message")
def tag(name: str, commit_ref: Optional[str], message: Optional[str]) -> None:
    """Tag a commit with a name. Uses latest commit if no ref given."""
    store = _get_store()

    if commit_ref is None:
        commits = store.log(limit=1)
        if not commits:
            err_console.print("[red]Error:[/red] No commits to tag.")
            sys.exit(1)
        commit_ref = commits[0].id

    try:
        t = store.tag(name, commit_ref, message)
    except ValueError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    console.print(
        f"[green]Tagged[/green] [{_short_id(t.commit_id)}] as [bold magenta]{t.name}[/bold magenta]"
        + (f": {t.message}" if t.message else "")
    )


@main.command()
def status() -> None:
    """Show currently staged prompts."""
    store = _get_store()
    staged = store.status()
    tracked = store.list_files()

    if not staged and not tracked:
        console.print("[dim]Nothing staged, no tracked prompts.[/dim]")
        return

    if staged:
        table = Table(title="Staged Prompts", header_style="bold green", border_style="green")
        table.add_column("Prompt Name", style="bold cyan")
        table.add_column("Size (chars)", justify="right")
        for name, content in staged.items():
            table.add_row(name, str(len(content)))
        console.print(table)
    else:
        console.print("[dim]Nothing staged.[/dim]")

    if tracked:
        console.print()
        t2 = Table(title="Tracked Prompts", header_style="bold blue", border_style="blue")
        t2.add_column("Prompt Name", style="bold cyan")
        t2.add_column("Current Commit", style="yellow")
        for f in tracked:
            t2.add_row(f.name, _short_id(f.current_commit_id) if f.current_commit_id else "-")
        console.print(t2)


@main.command()
@click.argument("commit_ref")
def show(commit_ref: str) -> None:
    """Show full details of a commit."""
    store = _get_store()
    commit = store.get_commit(commit_ref) or store.get_commit_by_tag(commit_ref)

    if not commit:
        err_console.print(f"[red]Error:[/red] Commit '{commit_ref}' not found.")
        sys.exit(1)

    meta_lines = [
        f"[bold]Commit:[/bold]  [yellow]{commit.id}[/yellow]",
        f"[bold]Prompt:[/bold]  [cyan]{commit.prompt_name}[/cyan]",
        f"[bold]Message:[/bold] {commit.message}",
        f"[bold]Date:[/bold]    {commit.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]
    if commit.parent_id:
        meta_lines.append(f"[bold]Parent:[/bold]  [yellow]{_short_id(commit.parent_id)}[/yellow]")
    if commit.model:
        meta_lines.append(f"[bold]Model:[/bold]   [blue]{commit.model}[/blue]")
    if commit.temperature is not None:
        meta_lines.append(f"[bold]Temp:[/bold]    {commit.temperature}")
    if commit.tags:
        meta_lines.append(f"[bold]Tags:[/bold]    [magenta]{', '.join(commit.tags)}[/magenta]")
    if commit.notes:
        meta_lines.append(f"[bold]Notes:[/bold]   [dim]{commit.notes}[/dim]")

    console.print(
        Panel(
            "\n".join(meta_lines),
            title="Commit Details",
            border_style="yellow",
        )
    )
    console.print()
    console.print(Panel(commit.content, title="Prompt Content", border_style="dim"))
