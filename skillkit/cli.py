"""skillkit command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skillkit import __version__
from skillkit.config import (
    ConfigError,
    effective_settings,
    find_repo,
    load_local,
    reset_settings,
    write_settings,
)
from skillkit.index import format_matches, load_index, search, write_index
from skillkit.install import (
    doctor_links,
    install_skills,
    remember_workspace,
    resolve_workspace,
)
from skillkit.skills import (
    add_skill,
    discover,
    find_skill,
    move_skill,
    remove_skill,
    set_invocation,
    validate_repo,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skillkit", description="Maintain a portable Agent Skills library.")
    parser.add_argument("--version", action="version", version=f"skillkit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Check skill files against the Agent Skills rules")
    sub.add_parser("index", help="Rebuild catalog/index.yaml from frontmatter")
    sub.add_parser("doctor", help="Check links, the custom root, and the index")

    find_parser = sub.add_parser("find", help="Search the catalog and print a few matches")
    find_parser.add_argument("query")
    find_parser.add_argument("--limit", type=int, default=5)

    add_parser = sub.add_parser("add", help="Create a skill from the skeleton")
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--category", default="")
    add_parser.add_argument("--root", default="custom")
    add_parser.add_argument("--phase", action="append", default=[])

    remove_parser = sub.add_parser("remove", help="Delete a skill")
    remove_parser.add_argument("name")

    move_parser = sub.add_parser("move", help="Change a skill's category or root")
    move_parser.add_argument("name")
    move_parser.add_argument("--category", required=True)
    move_parser.add_argument("--root", default=None)

    enable_parser = sub.add_parser("enable", help="Set a skill to library, manual, or auto")
    enable_parser.add_argument("name")
    enable_parser.add_argument("state", choices=["library", "manual", "auto"])

    disable_parser = sub.add_parser("disable", help="Set a skill back to library (not linked)")
    disable_parser.add_argument("name")

    install_parser = sub.add_parser("install", help="Link manual and auto skills into IDE folders")
    install_parser.add_argument("--workspace", type=Path, default=None)

    reset_parser = sub.add_parser("reset", help="Copy defaults onto settings and relink")
    reset_parser.add_argument("--workspace", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    repo = find_repo()
    if args.command == "validate":
        return _validate(repo)
    if args.command == "doctor":
        return doctor(repo)
    if args.command == "index":
        _reindex(repo)
        print(f"Wrote {repo / 'catalog' / 'index.yaml'}")
        return 0
    if args.command == "find":
        _ensure_index(repo)
        matches = search(load_index(repo), args.query, limit=args.limit)
        print(format_matches(matches))
        return 0
    if args.command == "add":
        settings = effective_settings(repo)
        skill = add_skill(
            repo,
            settings,
            name=args.name,
            description=args.description,
            category=args.category,
            root=args.root,
            phases=args.phase,
        )
        errors = validate_repo(repo, discover(repo, settings))
        _reindex(repo)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"Added {skill.rel_posix} in library state. Enable it to show /{skill.name}.")
        return 0
    if args.command == "remove":
        settings = effective_settings(repo)
        skill = find_skill(discover(repo, settings), args.name)
        remove_skill(skill)
        skills_map = dict(settings.get("skills") or {})
        skills_map.pop(args.name, None)
        _save_skill_states(repo, skills_map)
        _reindex(repo)
        _relink(repo)
        print(f"Removed {args.name}.")
        return 0
    if args.command == "move":
        settings = effective_settings(repo)
        skill = find_skill(discover(repo, settings), args.name)
        moved = move_skill(skill, args.category, args.root, repo)
        _reindex(repo)
        _relink(repo)
        print(f"Moved {args.name} to {moved.rel_posix}.")
        return 0
    if args.command == "enable":
        return _set_state(repo, args.name, args.state)
    if args.command == "disable":
        return _set_state(repo, args.name, "library")
    if args.command == "install":
        return _install(repo, args.workspace, remember=True)
    if args.command == "reset":
        reset_settings(repo)
        print("Restored settings from defaults.")
        return _install(repo, args.workspace, remember=args.workspace is not None)
    parser_fallback = 2
    return parser_fallback


def _validate(repo: Path) -> int:
    errors = validate_repo(repo, discover(repo, effective_settings(repo)))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Skills are valid.")
    return 0


def _reindex(repo: Path) -> None:
    write_index(repo, discover(repo, effective_settings(repo)))


def _set_state(repo: Path, name: str, state: str) -> int:
    settings = effective_settings(repo)
    skills = discover(repo, settings)
    skill = find_skill(skills, name)
    set_invocation(skill, state)
    from skillkit.config import load_config

    stored = load_config(repo)["settings"]
    skill_states = dict(stored.get("skills") or {})
    if state == "library":
        skill_states.pop(name, None)
    else:
        skill_states[name] = state
    stored["skills"] = skill_states
    write_settings(repo, stored)
    _relink(repo)
    print(f"{name} is {state}.")
    return 0


def _save_skill_states(repo: Path, skill_states: dict) -> None:
    from skillkit.config import load_config

    stored = load_config(repo)["settings"]
    stored["skills"] = skill_states
    write_settings(repo, stored)


def _install(repo: Path, workspace_arg: Path | None, remember: bool) -> int:
    settings = effective_settings(repo)
    workspace = resolve_workspace(settings, workspace_arg, repo)
    if settings.get("scope") == "workspace" and workspace is None:
        print(
            "error: pass --workspace PATH, or set workspace in skills.config.local.yaml.",
            file=sys.stderr,
        )
        return 1
    if remember and workspace is not None:
        remember_workspace(repo, workspace)
        settings = effective_settings(repo)
        workspace = resolve_workspace(settings, workspace, repo)
    notes = install_skills(repo, settings, discover(repo, settings), workspace)
    for note in notes:
        print(note)
    if not notes:
        print("No manual or auto skills to link.")
    return 0


def _relink(repo: Path) -> None:
    settings = effective_settings(repo)
    workspace = resolve_workspace(settings, None, repo)
    if settings.get("scope") == "workspace" and workspace is None:
        return
    install_skills(repo, settings, discover(repo, settings), workspace)


def _ensure_index(repo: Path) -> None:
    if not (repo / "catalog" / "index.yaml").is_file():
        _reindex(repo)


def doctor(repo: Path | None = None) -> int:
    repo = repo or find_repo()
    _ensure_index(repo)
    settings = effective_settings(repo)
    skills = discover(repo, settings)
    failures: list[str] = []
    notices: list[str] = []

    local = load_local(repo)
    roots = local.get("roots") if isinstance(local.get("roots"), list) else settings.get("roots")
    if isinstance(roots, list) and "custom" in roots:
        custom = repo / "custom"
        if not custom.is_dir():
            notices.append("custom/ is not created yet. skillkit add creates it.")

    indexed = {record.get("path") for record in load_index(repo)}
    for skill in skills:
        if skill.rel_posix not in indexed:
            failures.append(f"{skill.rel_posix} is not in the catalog. Run skillkit index.")

    workspace = resolve_workspace(settings, None, repo)
    link_failures, link_notices = doctor_links(settings, skills, workspace)
    failures.extend(link_failures)
    notices.extend(link_notices)

    for notice in notices:
        print(f"notice: {notice}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Library looks consistent.")
    return 0


