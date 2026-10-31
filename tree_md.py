#!/usr/bin/env python3
"""tree-md: print the contents of a directory as Markdown."""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence
from urllib.parse import quote

__version__ = "0.1.0"

DEFAULT_EXCLUDES = (
    ".git",
    ".hg",
    ".svn",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".DS_Store",
    "Thumbs.db",
)


@dataclass
class Node:
    """A directory or file in the scanned tree."""

    name: str
    path: Path
    is_dir: bool
    is_symlink: bool = False
    children: list["Node"] = field(default_factory=list)


def _is_dir(entry: os.DirEntry[str]) -> bool:
    """Return True only for real directories (never for symlinks)."""
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def _sort_key(entry: os.DirEntry[str]) -> tuple[bool, str, str]:
    """Sort directories first, then files, case-insensitively."""
    return (not _is_dir(entry), entry.name.casefold(), entry.name)


def is_excluded(name: str, rel_path: str, patterns: Sequence[str]) -> bool:
    """Return True when a name or root-relative path matches a pattern."""
    for pattern in patterns:
        if "/" in pattern:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        elif fnmatch.fnmatch(name, pattern):
            return True
    return False


def collect(
    root: Path,
    *,
    max_depth: int | None = None,
    excludes: Sequence[str] = (),
    dirs_only: bool = False,
    skip_paths: Sequence[Path] = (),
) -> tuple[Node, list[str]]:
    """Scan *root* and return its tree plus a list of unreadable paths."""
    root = Path(root)
    abs_root = Path(os.path.abspath(root))
    display_name = abs_root.name or abs_root.drive or str(abs_root)
    root_node = Node(display_name, abs_root, True)
    errors: list[str] = []
    skipped = {
        os.path.normcase(os.path.abspath(path)) for path in skip_paths
    }

    def scan(node: Node, depth: int) -> None:
        if max_depth is not None and depth >= max_depth:
            return

        try:
            with os.scandir(node.path) as iterator:
                entries = sorted(iterator, key=_sort_key)
        except OSError as exc:
            errors.append(f"{node.path}: {exc.strerror or exc}")
            return

        for entry in entries:
            entry_path = Path(entry.path)
            try:
                rel_path = entry_path.relative_to(abs_root).as_posix()
            except ValueError:
                rel_path = entry_path.as_posix()

            if is_excluded(entry.name, rel_path, excludes):
                continue
            if os.path.normcase(os.path.abspath(entry_path)) in skipped:
                continue

            is_dir = _is_dir(entry)
            if dirs_only and not is_dir:
                continue

            child = Node(
                name=entry.name,
                path=entry_path,
                is_dir=is_dir,
                is_symlink=entry.is_symlink(),
            )
            node.children.append(child)

            if is_dir:
                scan(child, depth + 1)

    scan(root_node, 0)
    return root_node, errors


def render_tree(root: Node) -> str:
    """Render the tree using box-drawing characters."""
    lines = [f"{root.name}/"]

    def walk(node: Node, prefix: str) -> None:
        count = len(node.children)
        for index, child in enumerate(node.children):
            last = index == count - 1
            connector = "└── " if last else "├── "
            if child.is_dir:
                suffix = "/"
            elif child.is_symlink:
                suffix = "@"
            else:
                suffix = ""
            lines.append(f"{prefix}{connector}{child.name}{suffix}")
            if child.children:
                walk(child, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines)


def _escape_md(text: str) -> str:
    """Escape characters that have a special meaning in Markdown labels."""
    for character in "\\`*_{}[]<>#|":
        text = text.replace(character, "\\" + character)
    return text


def _relative_link(path: Path, base: Path) -> str:
    """Return a URL-encoded, base-relative Markdown link target."""
    try:
        relative = os.path.relpath(path, base)
    except ValueError:
        # No relative path exists (for example, different Windows drives).
        return Path(os.path.abspath(path)).as_uri()
    return quote(Path(relative).as_posix(), safe="/")


def render_list(root: Node, link_base: Path) -> str:
    """Render a nested Markdown list. File names become links."""
    base = Path(os.path.abspath(link_base))
    lines = [f"- **{_escape_md(root.name)}/**"]

    def walk(node: Node, depth: int) -> None:
        for child in node.children:
            indent = "  " * depth
            if child.is_dir:
                lines.append(f"{indent}- **{_escape_md(child.name)}/**")
                walk(child, depth + 1)
            else:
                label = _escape_md(child.name) + ("@" if child.is_symlink else "")
                target = _relative_link(child.path, base)
                lines.append(f"{indent}- [{label}]({target})")

    walk(root, 1)
    return "\n".join(lines)


def count_entries(root: Node) -> tuple[int, int]:
    """Count directories and files below *root* (root itself is not counted)."""
    directories = 0
    files = 0
    stack = list(root.children)
    while stack:
        node = stack.pop()
        if node.is_dir:
            directories += 1
            stack.extend(node.children)
        else:
            files += 1
    return directories, files


def _summary(directories: int, files: int) -> str:
    directory_word = "directory" if directories == 1 else "directories"
    file_word = "file" if files == 1 else "files"
    return f"{directories} {directory_word}, {files} {file_word}"


def build_markdown(
    root: Node,
    *,
    fmt: str = "tree",
    title: str = "Directory Structure",
    link_base: Path | None = None,
    timestamp: bool = False,
) -> str:
    """Build the complete Markdown document."""
    blocks: list[str] = []

    if title:
        blocks.append(f"# {title}")
    if timestamp:
        now = datetime.now().astimezone()
        blocks.append(f"_Generated: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}_")

    if fmt == "tree":
        tree = render_tree(root)
        fence = "```"
        while fence in tree:
            fence += "`"
        blocks.append(f"{fence}text\n{tree}\n{fence}")
    elif fmt == "list":
        base = link_base if link_base is not None else Path.cwd()
        blocks.append(render_list(root, base))
    else:
        raise ValueError(f"unknown format: {fmt}")

    directories, files = count_entries(root)
    blocks.append(_summary(directories, files))
    return "\n\n".join(blocks) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tree-md",
        description="Print the contents of a directory as Markdown.",
        epilog=(
            "Examples:\n"
            "  tree-md\n"
            "  tree-md src --max-depth 2\n"
            "  tree-md . --format list -o STRUCTURE.md\n"
            "  tree-md . --exclude '*.log' --exclude tmp"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="directory to scan (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        type=Path,
        help="write Markdown to FILE instead of standard output",
    )
    parser.add_argument(
        "--format",
        choices=("tree", "list"),
        default="tree",
        help="output style: a text tree or a nested list with links (default: tree)",
    )
    title_group = parser.add_mutually_exclusive_group()
    title_group.add_argument(
        "--title",
        default="Directory Structure",
        metavar="TEXT",
        help="document heading (default: Directory Structure)",
    )
    title_group.add_argument(
        "--no-title",
        action="store_true",
        help="omit the document heading",
    )
    parser.add_argument(
        "--max-depth",
        metavar="N",
        type=int,
        help="limit recursion depth (0 shows only the root directory)",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        metavar="PATTERN",
        action="append",
        default=[],
        help=(
            "additional glob pattern to ignore; may be repeated. Patterns "
            "containing '/' match the root-relative path"
        ),
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="do not ignore .git, node_modules, caches, and virtualenvs",
    )
    parser.add_argument(
        "--dirs-only",
        action="store_true",
        help="show directories only",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="add the generation date and time (omitted by default for reproducible output)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _configure_console() -> None:
    """Prefer UTF-8 on standard streams so tree characters render everywhere."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_console()

    if args.max_depth is not None and args.max_depth < 0:
        parser.error("--max-depth must be 0 or greater")

    root = Path(args.path)
    if not root.exists():
        parser.error(f"path does not exist: {root}")
    if not root.is_dir():
        parser.error(f"path is not a directory: {root}")

    excludes: list[str] = (
        [] if args.no_default_excludes else list(DEFAULT_EXCLUDES)
    )
    for pattern in args.exclude:
        normalized = pattern.replace("\\", "/") if os.sep == "\\" else pattern
        if normalized not in excludes:
            excludes.append(normalized)

    skip_paths: list[Path] = []
    if args.output is not None:
        output_abs = Path(os.path.abspath(args.output))
        root_abs = Path(os.path.abspath(root))
        try:
            output_abs.relative_to(root_abs)
        except ValueError:
            pass
        else:
            # Do not list the file being generated on subsequent runs.
            skip_paths.append(output_abs)

    root_node, errors = collect(
        root,
        max_depth=args.max_depth,
        excludes=excludes,
        dirs_only=args.dirs_only,
        skip_paths=skip_paths,
    )
    for error in errors:
        print(f"warning: cannot read {error}", file=sys.stderr)

    link_base = args.output.parent if args.output else Path.cwd()
    markdown = build_markdown(
        root_node,
        fmt=args.format,
        title="" if args.no_title else args.title,
        link_base=link_base,
        timestamp=args.timestamp,
    )

    if args.output is not None:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(markdown)
        except OSError as exc:
            print(f"error: cannot write {args.output}: {exc}", file=sys.stderr)
            return 1
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
