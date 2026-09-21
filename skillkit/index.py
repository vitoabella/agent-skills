"""Build and search the skill catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

from skillkit.skills import Skill, public_skills

INDEX_NAME = "catalog/index.yaml"
LOCAL_INDEX_NAME = "catalog/index.local.yaml"
FIND_LIMIT = 5


def skill_record(skill: Skill) -> dict:
    return {
        "name": skill.name,
        "description": skill.description,
        "root": skill.root,
        "category": skill.category,
        "path": skill.rel_posix,
    }


def write_index(repo: Path, skills: list[Skill]) -> None:
    catalog = repo / "catalog"
    catalog.mkdir(exist_ok=True)
    _dump(catalog / "index.yaml", public_skills(skills))
    custom = [skill for skill in skills if skill.root == "custom"]
    local_path = repo / LOCAL_INDEX_NAME
    if custom:
        _dump(local_path, custom)
    elif local_path.is_file():
        local_path.unlink()


def load_index(repo: Path) -> list[dict]:
    records = _load(repo / INDEX_NAME)
    records.extend(_load(repo / LOCAL_INDEX_NAME))
    return records


def search(records: list[dict], query: str, limit: int = FIND_LIMIT) -> list[dict]:
    words = [word.lower() for word in query.split() if word.strip()]
    if not words:
        return []
    scored: list[tuple[int, dict]] = []
    for record in records:
        haystack = " ".join(
            [
                str(record.get("name") or ""),
                str(record.get("description") or ""),
                str(record.get("category") or ""),
                str(record.get("path") or ""),
            ]
        ).lower()
        if not all(word in haystack for word in words):
            continue
        name = str(record.get("name") or "").lower()
        score = 0
        if name == " ".join(words):
            score += 100
        if any(word in name for word in words):
            score += 10
        scored.append((score, record))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    return [record for _, record in scored[:limit]]


def format_matches(records: list[dict]) -> str:
    if not records:
        return "No matches."
    lines = []
    for record in records:
        lines.append(f"{record.get('name')}  {record.get('path')}")
        description = str(record.get("description") or "").strip()
        if description:
            lines.append(f"  {description}")
    return "\n".join(lines)


def _dump(path: Path, skills: list[Skill]) -> None:
    payload = {"skills": [skill_record(skill) for skill in skills]}
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, list):
        return []
    return [item for item in skills if isinstance(item, dict)]
