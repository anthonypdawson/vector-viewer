#!/usr/bin/env python3
"""Append a structured entry to docs/RELEASE_REASON.md for release notes.

Usage:
  scripts/add_release_reason.py --message "Short summary" [--type fix|feat|chore] [--detail-file details.md]

If no message is provided, reads from stdin.
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
from pathlib import Path


def git_commit_hash() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])  # type: ignore
        return out.decode().strip()
    except Exception:
        return ""


def git_user() -> str:
    try:
        name = subprocess.check_output(["git", "config", "user.name"]).decode().strip()  # type: ignore
        email = subprocess.check_output(["git", "config", "user.email"]).decode().strip()  # type: ignore
        return f"{name} <{email}>" if name or email else ""
    except Exception:
        return ""


def load_detail(detail_file: Path | None) -> str:
    if not detail_file:
        return ""
    try:
        return detail_file.read_text(encoding="utf-8").rstrip()
    except Exception:
        return ""


def prepend_release_reason(entry: str, file: Path = Path("docs/RELEASE_REASON.md")) -> None:
    # Ensure file exists
    if not file.exists():
        file.write_text("", encoding="utf-8")

    orig = file.read_text(encoding="utf-8")

    # If file uses the simple '# Latest updates' bullet list format,
    # insert a single bullet under that header to match existing style.
    lines = orig.splitlines()
    if lines:
        first = lines[0].strip()
    else:
        first = ""

    bullet = entry.strip()

    if first.startswith("#"):
        # Insert bullet after first header line, preserving any existing
        # bullets or separators. Keep '---' separator if present at end.
        rest = lines[1:]
        # If file already has a '---' separator at the end, keep it aside
        trailing_sep = []
        if rest and rest[-1].strip() == "---":
            trailing_sep = [rest[-1]]
            rest = rest[:-1]

        # Build new content: header + blank line + new bullet + existing rest + separator
        new_lines = [lines[0], "", f"- {bullet}"]
        if rest:
            # ensure a blank line between bullets and existing content if needed
            if rest[0].strip() != "":
                new_lines.append("")
            new_lines.extend(rest)
        if trailing_sep:
            new_lines.append("")
            new_lines.extend(trailing_sep)

        new = "\n".join(new_lines) + "\n"
    else:
        # Fallback to previous behavior: prepend full entry block
        new = entry.rstrip() + "\n\n" + orig

    file.write_text(new, encoding="utf-8")


def build_entry(message: str, kind: str, detail: str, commit: str, author: str) -> str:
    # For RELEASE_REASON.md we prefer a concise bullet-format entry. Keep the
    # message short; include commit hash in parentheses when available.
    commit_part = f" ({commit})" if commit else ""
    return f"{message}{commit_part}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--message", "-m", help="Short summary for release notes")
    p.add_argument("--type", "-t", choices=["fix", "feat", "chore"], default="fix")
    p.add_argument("--detail-file", "-d", help="Path to file with detailed notes")
    args = p.parse_args()

    if not args.message:
        # read from stdin
        if sys.stdin.isatty():
            print("Error: either --message or stdin must be provided", file=sys.stderr)
            sys.exit(2)
        msg = sys.stdin.read().strip()
    else:
        msg = args.message.strip()

    detail = load_detail(Path(args.detail_file)) if args.detail_file else ""
    commit = git_commit_hash()
    author = git_user()

    entry = build_entry(msg, args.type, detail, commit, author)
    prepend_release_reason(entry, Path("docs/RELEASE_REASON.md"))
    print("Appended release reason.")


if __name__ == "__main__":
    main()
