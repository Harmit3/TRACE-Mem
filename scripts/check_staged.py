"""Reject staged private artifacts and recognizable secrets without printing them."""

from pathlib import PurePosixPath
import re
import subprocess
import sys


SECRET = re.compile(
    rb"(?i)(?:sk-(?:proj-|or-v1-)?[a-z0-9_-]{20,}|"
    rb"gh[pousr]_[a-z0-9]{24,}|github_pat_[a-z0-9_]{35,}|"
    rb"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    rb"(?:OPENAI|OPENROUTER)_API_KEY\s*=\s*['\"]?[^\s'\"]+)"
)


def forbidden(path: str, content: bytes) -> bool:
    file = PurePosixPath(path.casefold())
    if (file.parts[0] in {"data", "results", "third_party"}
            or file.suffix in {".pem", ".key", ".db", ".sqlite", ".sqlite3"}
            or ".sqlite-" in file.name or ".sqlite3-" in file.name or ".db-" in file.name):
        return True
    if file.name == ".env.example":
        return any(not re.fullmatch(rb"[A-Z][A-Z0-9_]*", line) for line in content.splitlines())
    return file.name.startswith(".env") or SECRET.search(content) is not None


def main() -> int:
    changes = subprocess.check_output(["git", "diff", "--cached", "--name-only",
                                       "--diff-filter=ACMRT", "-z"])
    blocked = 0
    for path in changes.decode("utf-8", errors="surrogateescape").split("\0"):
        if path and forbidden(path, subprocess.check_output(["git", "show", f":{path}"])):
            blocked += 1
    if blocked:
        print(f"Commit blocked: {blocked} staged file(s) match private-data or secret rules.",
              file=sys.stderr)
    return int(bool(blocked))


if __name__ == "__main__":
    raise SystemExit(main())
