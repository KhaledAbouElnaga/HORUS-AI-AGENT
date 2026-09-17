"""Dependency-free tracked-file secret pattern scan for CI/review evidence."""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

PATTERNS = [
    r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----",
    r"gh[pousr]_[A-Za-z0-9_]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"AIza[0-9A-Za-z_-]{20,}",
    r"xox[baprs]-[0-9A-Za-z-]{20,}",
    r"bearer[ \t]+[A-Za-z0-9._-]{20,}",
    r"(?:api[_-]?key|secret|token|password)[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_./+=-]{20,}",
]


def main() -> int:
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    tracked = [pathlib.Path(name) for name in names if name and pathlib.Path(name).is_file()]
    regex = re.compile("|".join(f"(?:{pattern})" for pattern in PATTERNS), re.IGNORECASE)
    hits = []
    for path in tracked:
        for line_number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if regex.search(line):
                hits.append(f"{path}:{line_number}:{line.strip()}")
    print(f"tracked files scanned: {len(tracked)}")
    print(f"secret-pattern matches: {len(hits)}")
    for hit in hits:
        print(hit)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
