"""Load and write skills.config.yaml plus the gitignored local overlay."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import yaml

CONFIG_NAME = "skills.config.yaml"
LOCAL_NAME = "skills.config.local.yaml"
HEADER = (
    "# Edit settings by hand or via skillkit. "
    "skillkit reset copies defaults onto settings.\n"
    "# This machine's workspace path and custom root belong in "
    "skills.config.local.yaml.\n"
)


class ConfigError(RuntimeError):
    pass


def find_repo(start: Path | None = None) -> Path:
    env = os.environ.get("SKILLKIT_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if (root / CONFIG_NAME).is_file():
            return root
        raise ConfigError(f"SKILLKIT_ROOT does not contain {CONFIG_NAME}: {root}")

    search_from = [Path.cwd()]
    if start is not None:
        search_from.append(start)
    search_from.append(Path(__file__).resolve().parents[1])

    seen: set[Path] = set()
    for origin in search_from:
        current = origin.resolve()
        while True:
            if current in seen:
                break
            seen.add(current)
            if (current / CONFIG_NAME).is_file():
                return current
            if current.parent == current:
                break
            current = current.parent
    raise ConfigError(
        f"Could not find {CONFIG_NAME}. Run skillkit from the kit repo, "
        "or set SKILLKIT_ROOT."
    )


def load_config(repo: Path) -> dict:
    path = repo / CONFIG_NAME
    data = _read_yaml(path)
    if not isinstance(data, dict) or "defaults" not in data or "settings" not in data:
        raise ConfigError(f"{path} must contain defaults and settings mappings.")
    if not isinstance(data["defaults"], dict) or not isinstance(data["settings"], dict):
        raise ConfigError(f"{path} defaults and settings must be mappings.")
    return data


def load_local(repo: Path) -> dict:
    path = repo / LOCAL_NAME
    if not path.is_file():
        return {}
    data = _read_yaml(path)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must be a mapping.")
    return data


def effective_settings(repo: Path) -> dict:
    """settings with skills.config.local.yaml keys overlaid."""
    config = load_config(repo)
    settings = deepcopy(config["settings"])
    local = load_local(repo)
    for key, value in local.items():
        settings[key] = value
    _require_settings(settings)
    return settings


def write_settings(repo: Path, settings: dict) -> None:
    config = load_config(repo)
    rendered = HEADER + yaml.safe_dump(
        {"defaults": config["defaults"], "settings": settings},
        sort_keys=False,
        allow_unicode=True,
    )
    (repo / CONFIG_NAME).write_text(rendered, encoding="utf-8")


def write_local(repo: Path, local: dict) -> None:
    text = yaml.safe_dump(local, sort_keys=False, allow_unicode=True)
    (repo / LOCAL_NAME).write_text(text, encoding="utf-8")


def reset_settings(repo: Path) -> dict:
    config = load_config(repo)
    settings = deepcopy(config["defaults"])
    write_settings(repo, settings)
    return effective_settings(repo)


def _read_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc


def _require_settings(settings: dict) -> None:
    if settings.get("scope") not in {"workspace", "user"}:
        raise ConfigError("settings.scope must be workspace or user.")
    roots = settings.get("roots")
    if not isinstance(roots, list) or not all(isinstance(item, str) for item in roots):
        raise ConfigError("settings.roots must be a list of root names.")
    skills = settings.get("skills")
    if not isinstance(skills, dict):
        raise ConfigError("settings.skills must be a mapping of name to state.")
    for name, state in skills.items():
        if state not in {"library", "manual", "auto"}:
            raise ConfigError(
                f"settings.skills.{name} must be library, manual, or auto."
            )
