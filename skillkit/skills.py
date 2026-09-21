"""Discover skills, check them, and create or move them."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from skillkit.config import ConfigError

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DESCRIPTION_MAX = 1024
IDE_SKILL_PARENTS = {".cursor", ".agents", ".claude", ".codex", ".github"}
MODULE_RE = re.compile(r"modules/([A-Za-z0-9_.-]+\.md)")

ONE_PHASE = (
    "Describe the procedure the agent should follow. "
    "Keep supporting detail in references/ or scripts/ and name those files here "
    "when the agent should open them."
)


@dataclass
class Skill:
    name: str
    description: str
    root: str
    category: str
    path: Path
    frontmatter: dict = field(default_factory=dict)
    body: str = ""

    @property
    def rel_posix(self) -> str:
        parts = [self.root]
        if self.category:
            parts.append(self.category)
        parts.append(self.name)
        return "/".join(parts)


def parse_skill_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ConfigError(f"{path} is missing YAML frontmatter.")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ConfigError(f"{path} must start with a --- frontmatter fence.")
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        raise ConfigError(f"{path} frontmatter is not closed.")
    raw = "".join(lines[1:end])
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid frontmatter in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} frontmatter must be a mapping.")
    body = "".join(lines[end + 1 :])
    return data, body


def skill_from_dir(skill_dir: Path, root_name: str, root_dir: Path) -> Skill:
    frontmatter, body = parse_skill_file(skill_dir / "SKILL.md")
    rel = skill_dir.relative_to(root_dir)
    category = "" if rel.parent == Path(".") else rel.parent.as_posix()
    description = frontmatter.get("description")
    return Skill(
        name=str(frontmatter.get("name") or skill_dir.name),
        description=description.strip() if isinstance(description, str) else "",
        root=root_name,
        category=category,
        path=skill_dir,
        frontmatter=frontmatter,
        body=body,
    )


def configured_roots(repo: Path, settings: dict) -> list[str]:
    roots = list(settings.get("roots") or [])
    for required in ("meta", "shared"):
        if required not in roots:
            roots.append(required)
    return roots


def present_root_dirs(repo: Path, root_names: list[str]) -> list[tuple[str, Path]]:
    found = []
    for name in root_names:
        path = repo / name
        if path.is_dir() and _root_is_available(path):
            found.append((name, path))
    return found


def _root_is_available(path: Path) -> bool:
    """A root is available when its directory exists."""
    return path.is_dir()


def discover(repo: Path, settings: dict) -> list[Skill]:
    skills: list[Skill] = []
    for root_name, root_dir in present_root_dirs(repo, configured_roots(repo, settings)):
        for skill_md in sorted(root_dir.rglob("SKILL.md")):
            if "modules" in skill_md.relative_to(root_dir).parts:
                continue
            skills.append(skill_from_dir(skill_md.parent, root_name, root_dir))
    return skills


def public_skills(skills: list[Skill]) -> list[Skill]:
    return [skill for skill in skills if skill.root != "custom"]


def find_skill(skills: list[Skill], name: str) -> Skill:
    matches = [skill for skill in skills if skill.name == name]
    if not matches:
        raise ConfigError(f"No skill named {name!r}.")
    if len(matches) > 1:
        places = ", ".join(skill.rel_posix for skill in matches)
        raise ConfigError(f"More than one skill is named {name!r}: {places}")
    return matches[0]


def validate_name(name: str) -> str | None:
    if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
        return (
            "name must be 1-64 characters of lowercase letters, numbers, "
            "and single hyphens, and must not start or end with a hyphen"
        )
    return None


def validate_skill(skill: Skill) -> list[str]:
    errors: list[str] = []
    label = skill.rel_posix
    name_error = validate_name(skill.name)
    if name_error:
        errors.append(f"{label}: {name_error}")
    if skill.path.name != skill.frontmatter.get("name"):
        errors.append(
            f"{label}: frontmatter name {skill.frontmatter.get('name')!r} "
            f"must match the folder {skill.path.name!r}"
        )
    description = skill.frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{label}: description is required")
    elif len(description.strip()) > DESCRIPTION_MAX:
        errors.append(
            f"{label}: description is {len(description.strip())} characters; "
            f"the Agent Skills spec allows {DESCRIPTION_MAX}"
        )
    mentioned = set(MODULE_RE.findall(skill.body))
    modules_dir = skill.path / "modules"
    if modules_dir.is_dir():
        for module in sorted(modules_dir.glob("*.md")):
            if module.name not in mentioned:
                errors.append(
                    f"{label}: modules/{module.name} is not mentioned in SKILL.md"
                )
    for module_name in sorted(mentioned):
        if not (modules_dir / module_name).is_file():
            errors.append(f"{label}: SKILL.md points at missing modules/{module_name}")
    return errors


def validate_repo(repo: Path, skills: list[Skill]) -> list[str]:
    errors: list[str] = []
    for skill in skills:
        errors.extend(validate_skill(skill))
    names: dict[str, list[str]] = {}
    for skill in skills:
        names.setdefault(skill.name, []).append(skill.rel_posix)
    for name, places in sorted(names.items()):
        if len(places) > 1:
            errors.append(f"duplicate skill name {name!r}: {', '.join(places)}")
    for parent in IDE_SKILL_PARENTS:
        for found in repo.rglob(parent):
            if not found.is_dir():
                continue
            skills_dir = found / "skills"
            if skills_dir.exists():
                errors.append(
                    f"IDE skill folder inside the kit repo: {skills_dir.relative_to(repo)}"
                )
    return errors


def render_skill(repo: Path, name: str, description: str, phases: list[str]) -> str:
    template = (repo / "templates" / "skill" / "SKILL.md").read_text(encoding="utf-8")
    if phases:
        lines = [
            "Read one module, then follow it.",
            "",
        ]
        for phase in phases:
            lines.append(f"- Read `modules/{phase}.md` when working on {phase}.")
        instructions = "\n".join(lines)
    else:
        instructions = ONE_PHASE
    return (
        template.replace("{{name}}", name)
        .replace("{{description}}", description)
        .replace("{{instructions}}", instructions)
    )


def add_skill(
    repo: Path,
    settings: dict,
    name: str,
    description: str,
    category: str,
    root: str,
    phases: list[str],
) -> Skill:
    name_error = validate_name(name)
    if name_error:
        raise ConfigError(name_error)
    if not isinstance(description, str) or not description.strip():
        raise ConfigError("description is required")
    if len(description.strip()) > DESCRIPTION_MAX:
        raise ConfigError(
            f"description is {len(description.strip())} characters; "
            f"the Agent Skills spec allows {DESCRIPTION_MAX}"
        )
    if root not in configured_roots(repo, settings):
        raise ConfigError(
            f"Root {root!r} is not active. Add it under roots in "
            "skills.config.local.yaml, or pass --root shared."
        )
    root_dir = repo / root
    root_dir.mkdir(parents=True, exist_ok=True)
    category = _clean_category(category)
    for phase in phases:
        if validate_name(phase):
            raise ConfigError(
                f"phase {phase!r} must be a lowercase hyphenated name so the module file is safe"
            )
    dest = root_dir / category / name if category else root_dir / name
    if dest.exists():
        raise ConfigError(f"{dest} already exists")
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text(
        render_skill(repo, name, description.strip(), phases),
        encoding="utf-8",
    )
    for phase in phases:
        module_dir = dest / "modules"
        module_dir.mkdir(exist_ok=True)
        (module_dir / f"{phase}.md").write_text(
            f"# {phase}\n\nWrite the steps for this phase.\n",
            encoding="utf-8",
        )
    return skill_from_dir(dest, root, root_dir)


def remove_skill(skill: Skill) -> None:
    if (skill.path / "SKILL.md").is_file():
        shutil.rmtree(skill.path)
    parent = skill.path.parent
    root_dir = _root_dir(skill)
    while parent != root_dir and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def move_skill(skill: Skill, category: str, root: str | None, repo: Path) -> Skill:
    dest_root_name = root or skill.root
    dest_root = repo / dest_root_name
    dest_root.mkdir(parents=True, exist_ok=True)
    category = _clean_category(category)
    dest = dest_root / category / skill.name if category else dest_root / skill.name
    if dest.resolve() == skill.path.resolve():
        return skill
    if dest.exists():
        raise ConfigError(f"{dest} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(skill.path), str(dest))
    old_parent = skill.path.parent
    old_root = repo / skill.root
    parent = old_parent
    while parent != old_root and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    return skill_from_dir(dest, dest_root_name, dest_root)


def set_invocation(skill: Skill, state: str) -> None:
    """manual skills set disable-model-invocation. auto skills omit it."""
    if state == "library":
        return
    frontmatter, body = parse_skill_file(skill.path / "SKILL.md")
    if state == "manual":
        if frontmatter.get("disable-model-invocation") is True:
            return
        frontmatter["disable-model-invocation"] = True
    else:
        if "disable-model-invocation" not in frontmatter:
            return
        frontmatter.pop("disable-model-invocation", None)
    _write_frontmatter(skill.path / "SKILL.md", frontmatter, body)


def _write_frontmatter(path: Path, frontmatter: dict, body: str) -> None:
    dumped = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    if body and not body.startswith("\n"):
        body = "\n" + body
    text = f"---\n{dumped}\n---{body}"
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _clean_category(category: str) -> str:
    category = (category or "").strip().replace("\\", "/").strip("/")
    if category in {"", "."}:
        return ""
    parts = category.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ConfigError(f"category {category!r} must be a relative path without ..")
    return "/".join(parts)


def _root_dir(skill: Skill) -> Path:
    current = skill.path
    if skill.category:
        for _ in skill.category.split("/"):
            current = current.parent
        return current
    return skill.path.parent
