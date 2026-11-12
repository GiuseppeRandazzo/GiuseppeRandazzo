"""Automatically updates the recent repositories table in README.md."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
README_PATH = ROOT_DIR / "README.md"

START_MARKER = "<!-- AUTO-REPOS:START -->"
END_MARKER = "<!-- AUTO-REPOS:END -->"

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "GiuseppeRandazzo")
MAX_REPOS = int(os.environ.get("MAX_REPOS", "6"))


def fetch_repositories(owner: str) -> list[dict]:
    """Fetch public non-fork repositories sorted by most recent push."""
    url = f"https://api.github.com/users/{owner}/repos?per_page=100&sort=pushed&direction=desc"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{owner}-readme-updater",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        repos = json.loads(resp.read().decode("utf-8"))

    filtered = [
        r
        for r in repos
        if not r.get("fork")
        and not r.get("archived")
        and not r.get("private")
        and r.get("name", "").lower() != owner.lower()
    ]
    filtered.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    return filtered[:MAX_REPOS]


def format_description(text: str | None, max_len: int = 120) -> str:
    """Sanitize and truncate repository description for a Markdown table."""
    if not text or not text.strip():
        return "Progetto disponibile su GitHub."
    cleaned = " ".join(text.replace("|", "\\|").split())
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[: max_len - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def resolve_live_url(repo: dict, owner: str) -> str | None:
    """Return the homepage or GitHub Pages URL if available."""
    homepage = (repo.get("homepage") or "").strip()
    if homepage:
        return homepage
    if repo.get("has_pages"):
        return f"https://{owner.lower()}.github.io/{repo['name']}/"
    return None


def format_date(iso_timestamp: str | None) -> str:
    """Format ISO date string as DD/MM/YYYY."""
    if not iso_timestamp:
        return "—"
    dt = datetime.strptime(iso_timestamp[:10], "%Y-%m-%d")
    return dt.strftime("%d/%m/%Y")


def build_table(repos: list[dict], owner: str) -> str:
    """Build the Markdown table for recent repositories."""
    lines = [
        "| Repository | Descrizione | Linguaggio | Aggiornato |",
        "| :--- | :--- | :---: | :---: |",
    ]
    for repo in repos:
        name = repo["name"]
        url = repo["html_url"]
        live_url = resolve_live_url(repo, owner)
        repo_cell = f"**[{name}]({url})**"
        if live_url:
            repo_cell += f" · [Demo]({live_url})"

        desc_cell = format_description(repo.get("description"))
        lang = repo.get("language")
        lang_cell = f"`{lang}`" if lang else "—"
        date_cell = format_date(repo.get("pushed_at"))

        lines.append(f"| {repo_cell} | {desc_cell} | {lang_cell} | {date_cell} |")

    return "\n".join(lines)


def update_readme(content: str, generated_block: str) -> str:
    """Replace the delimited AUTO-REPOS section inside README content."""
    pattern = re.compile(
        rf"({re.escape(START_MARKER)})(.*?)({re.escape(END_MARKER)})",
        flags=re.DOTALL,
    )
    if not pattern.search(content):
        raise ValueError(f"Markers {START_MARKER} / {END_MARKER} not found in {README_PATH}")

    replacement = f"{START_MARKER}\n{generated_block}\n{END_MARKER}"
    return pattern.sub(lambda _: replacement, content, count=1)


def main() -> int:
    repos = fetch_repositories(OWNER)
    table = build_table(repos, OWNER)
    original = README_PATH.read_text(encoding="utf-8")
    updated = update_readme(original, table)

    if updated == original:
        print("README.md is already up to date.")
        return 0

    README_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated README.md with {len(repos)} recent repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
