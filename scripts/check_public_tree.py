"""Allowlisted publication scan; errors report rule/path, never matched secrets."""

from __future__ import annotations

import re
from pathlib import Path

DOMAIN = "haval_h6_th_location_tracker"
EXCLUDED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "dist"}
ROOT_FILES = {
    ".gitignore", "LICENSE", "README.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md",
    "hacs.json", "package.json", "package-lock.json", "pyproject.toml", "requirements-dev.txt",
}
IMAGES = {
    f"custom_components/{DOMAIN}/brand/icon.png",
    *(f"docs/images/{name}.png" for name in ("setup", "journeys", "stops", "no-gps")),
}
TEXT = {".py", ".js", ".mjs", ".css", ".html", ".json", ".yaml", ".yml", ".md", ".toml", ".txt"}
RULES = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----\s+[A-Za-z0-9+/]{24}"),
    "github-token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "JWT": re.compile(rb"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    "owner-endpoint": re.compile(rb"(?:synology\.me|hotmail\.com)", re.I),
    "private-LAN": re.compile(rb"\b192\.168\.[0-9]{1,3}\.[0-9]{1,3}\b"),
    "owner-path": re.compile(rb"(?:[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_-]+|OneDrive[ ]-[ ]Microsoft|session[-]state)", re.I),
}


def scan(root: Path) -> list[Path]:
    files = sorted(path for path in root.rglob("*") if (
        not set(path.relative_to(root).parts) & EXCLUDED and (path.is_file() or path.is_symlink())
    ))
    problems = []
    for path in files:
        relative = path.relative_to(root)
        name = relative.as_posix()
        allowed = (
            len(relative.parts) == 1 and name in ROOT_FILES
            or relative.parts[0] in {"docs", "scripts", "tests", "dashboards", ".github"}
            or relative.parts[:2] == ("custom_components", DOMAIN)
        )
        if path.is_symlink() or not allowed or (
            path.suffix not in TEXT and name not in ROOT_FILES and name not in IMAGES
        ):
            problems.append(f"{name}: unexpected publication member")
            continue
        payload = path.read_bytes()
        if len(payload) > 2 * 1024 * 1024:
            problems.append(f"{name}: publication member too large")
        if name in IMAGES:
            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                problems.append(f"{name}: expected PNG")
            offset = 8
            while offset + 12 <= len(payload):
                length = int.from_bytes(payload[offset:offset + 4])
                if payload[offset + 4:offset + 8] in {b"tEXt", b"iTXt", b"zTXt", b"eXIf"}:
                    problems.append(f"{name}: unexpected image metadata")
                offset += length + 12
        else:
            try:
                payload.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{name}: unexpected binary")
        problems.extend(f"{name}: {rule}" for rule, pattern in RULES.items() if pattern.search(payload))
    if problems:
        raise ValueError("\n".join(problems))
    return files


if __name__ == "__main__":
    print(f"Public-tree scan passed: {len(scan(Path(__file__).resolve().parents[1]))} allowlisted files")
