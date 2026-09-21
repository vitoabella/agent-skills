"""Point IDE skill folders at canonical skill directories."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from skillkit.config import ConfigError, load_local, write_local
from skillkit.skills import Skill, set_invocation

MANAGED_NAME = ".skillkit-managed"
GITIGNORE_START = "# skillkit-start"
GITIGNORE_END = "# skillkit-end"


def link_roots(scope: str, workspace: Path | None) -> list[Path]:
    if scope == "user":
        home = Path.home()
        return [
            home / ".claude" / "skills",
            home / ".gemini" / "config" / "skills",
            home / ".copilot" / "skills",
        ]
    if workspace is None:
        raise ConfigError("workspace scope needs a workspace path.")
    return [
        workspace / ".claude" / "skills",
        workspace / ".agents" / "skills",
    ]


def managed_path(scope: str, workspace: Path | None) -> Path:
    if scope == "user":
        return Path.home() / MANAGED_NAME
    if workspace is None:
        raise ConfigError("workspace scope needs a workspace path.")
    return workspace / MANAGED_NAME


def resolve_workspace(settings: dict, explicit: Path | None, repo: Path) -> Path | None:
    if settings.get("scope") == "user":
        return None
    raw = explicit or _workspace_from_settings(settings)
    if raw is None:
        return None
    workspace = Path(raw).expanduser().resolve()
    if workspace == repo or repo in workspace.parents:
        raise ConfigError(
            "Refusing to install into the kit repo. IDE folders there would "
            "load the linked skills while you edit them."
        )
    return workspace


def remember_workspace(repo: Path, workspace: Path) -> None:
    local = load_local(repo)
    local["workspace"] = str(workspace)
    write_local(repo, local)


def install_skills(
    repo: Path,
    settings: dict,
    skills: list[Skill],
    workspace: Path | None,
) -> list[str]:
    scope = settings["scope"]
    states = settings.get("skills") or {}
    enabled = []
    for skill in skills:
        state = states.get(skill.name, "library")
        if state in {"manual", "auto"}:
            set_invocation(skill, state)
            enabled.append(skill)

    roots = link_roots(scope, workspace)
    desired: dict[Path, Path] = {}
    for root in roots:
        for skill in enabled:
            desired[root / skill.name] = skill.path.resolve()

    notes = []
    previous = _read_managed(managed_path(scope, workspace))
    for link in previous:
        if link not in desired and _is_reparse(link):
            _remove_link(link)
            notes.append(f"removed {link}")

    for link, target in desired.items():
        _ensure_link(link, target)
        notes.append(f"linked {link} -> {target}")

    _write_managed(managed_path(scope, workspace), scope, desired)
    if scope == "workspace" and workspace is not None:
        _update_gitignore(workspace, desired)
    return notes


def doctor_links(settings: dict, skills: list[Skill], workspace: Path | None) -> tuple[list[str], list[str]]:
    """Return (failures, notices)."""
    failures: list[str] = []
    notices: list[str] = []
    scope = settings.get("scope")
    if scope == "workspace" and workspace is None:
        notices.append("No workspace is set. Run skillkit install --workspace PATH.")
        return failures, notices

    roots = link_roots(scope, workspace)
    states = settings.get("skills") or {}
    enabled = [skill for skill in skills if states.get(skill.name) in {"manual", "auto"}]
    managed = set(_read_managed(managed_path(scope, workspace)))

    for root in roots:
        for skill in enabled:
            link = root / skill.name
            if not link.exists():
                failures.append(f"missing link {link}")
                continue
            if not _is_reparse(link):
                failures.append(f"{link} exists and is not a junction or symlink")
                continue
            target = _link_target(link)
            if target is None or not _same_path(target, skill.path):
                failures.append(f"{link} points at {target}, expected {skill.path}")

    for link in managed:
        if link.exists() and not _is_reparse(link):
            failures.append(f"managed path is not a link: {link}")
        elif link.exists() and _link_target(link) is None:
            failures.append(f"broken link {link}")

    if len(roots) > 1 and enabled:
        notices.append(
            "Cursor and Copilot read more than one of these folders, so each "
            "linked skill can appear twice in autocomplete: "
            + ", ".join(str(root) for root in roots)
        )
    return failures, notices


def _workspace_from_settings(settings: dict) -> str | None:
    value = settings.get("workspace")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _ensure_link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        current = _link_target(link)
        if current is not None and _same_path(current, target):
            return
        if not _is_reparse(link):
            raise ConfigError(f"{link} exists and is not a skillkit link. Move it aside and rerun install.")
        _remove_link(link)
    if os.name == "nt":
        command = f'cmd /c mklink /J "{link}" "{target}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise ConfigError(f"mklink failed for {link}: {detail}")
    else:
        link.symlink_to(target, target_is_directory=True)


def _remove_link(link: Path) -> None:
    if os.name == "nt":
        os.rmdir(link)
    else:
        link.unlink()


def _is_reparse(path: Path) -> bool:
    if os.name != "nt":
        return path.is_symlink()
    if not path.exists() and not path.is_symlink():
        return False
    import ctypes

    get_attrs = ctypes.windll.kernel32.GetFileAttributesW
    get_attrs.argtypes = [ctypes.c_wchar_p]
    get_attrs.restype = ctypes.c_uint32
    attrs = get_attrs(str(path))
    if attrs == 0xFFFFFFFF:
        return False
    file_attribute_reparse_point = 0x400
    return bool(attrs & file_attribute_reparse_point)


def _same_path(left: Path, right: Path) -> bool:
    return _normalize(left) == _normalize(right)


def _normalize(path: Path) -> str:
    text = str(path)
    if text.startswith("\\\\?\\"):
        text = text[4:]
    return os.path.normcase(os.path.normpath(text))


def _link_target(path: Path) -> Path | None:
    try:
        return Path(os.readlink(path))
    except OSError:
        return None


def _read_managed(path: Path) -> list[Path]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    links = data.get("links") if isinstance(data, dict) else None
    if not isinstance(links, list):
        return []
    return [Path(item) for item in links if isinstance(item, str)]


def _write_managed(path: Path, scope: str, desired: dict[Path, Path]) -> None:
    payload = {
        "scope": scope,
        "links": [str(link) for link in desired],
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _update_gitignore(workspace: Path, desired: dict[Path, Path]) -> None:
    gitignore = workspace / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    rels = [MANAGED_NAME]
    for link in desired:
        try:
            rels.append(link.relative_to(workspace).as_posix())
        except ValueError:
            continue
    block = "\n".join([GITIGNORE_START, *rels, GITIGNORE_END])
    start = existing.find(GITIGNORE_START)
    end = existing.find(GITIGNORE_END)
    if start != -1 and end != -1 and end > start:
        end = end + len(GITIGNORE_END)
        updated = existing[:start].rstrip() + "\n\n" + block + existing[end:]
    else:
        separator = "" if existing.endswith("\n") or existing == "" else "\n"
        prefix = existing + separator
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        updated = prefix + ("\n" if prefix.strip() else "") + block + "\n"
    gitignore.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
