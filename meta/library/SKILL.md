---
name: library
description: Search and maintain the skill library. Use when the user wants to find a skill, add or remove one, move it to another category, enable or disable it, install links into a workspace, or reset settings.
disable-model-invocation: true
---

# library

Run `skillkit` for every library change. Do not walk skill folders and do not open `catalog/index.yaml`. `skillkit find` prints a few paths and descriptions. Open a `SKILL.md` only after that command names it, or after the user names the skill.

The kit repo holds the files. IDE folders are junctions. Edit skills in the repo.

## Find

```text
skillkit find QUERY
```

Use the printed path. If there are no matches, say so and stop. Do not search the filesystem for another copy.

## Add

Follow `/create-skill` when the user is authoring a new skill. That command writes into `custom/` and leaves the skill unlinked.

## Remove

```text
skillkit remove NAME
```

This deletes the skill directory and drops its IDE links.

## Move

```text
skillkit move NAME --category CATEGORY
skillkit move NAME --category CATEGORY --root shared
```

`--root` changes which tree the skill lives in. Omit it to keep the current root. Category is the folder under that root, such as `school` or `github`.

## Enable and disable

```text
skillkit enable NAME manual
skillkit enable NAME auto
skillkit disable NAME
```

- `manual` shows `/NAME` and sets `disable-model-invocation: true`.
- `auto` shows `/NAME` and allows the IDE to select the skill from its description.
- `disable` sets the skill back to library state. It stays on disk and disappears from the slash menu.

New skills stay in library state until the user asks to enable them.

## Install

```text
skillkit install --workspace PATH
```

Links every manual and auto skill into that project's `.claude/skills` and `.agents/skills`. The path is stored in `skills.config.local.yaml`. Later installs can omit `--workspace`. Do not point `--workspace` at the kit repo.

User scope is `settings.scope: user` in `skills.config.yaml`. Install then links `~/.claude/skills`, `~/.gemini/config/skills`, and `~/.copilot/skills`.

## Reset

```text
skillkit reset
```

Copies `defaults` onto `settings` and relinks. It does not change `skills.config.local.yaml` or files under `custom/`.

## Config

Edit `settings` in `skills.config.yaml`, or let these commands write that block. Leave `defaults` as the reset baseline. Machine-specific keys (`workspace`, and `roots` including `custom`) belong in `skills.config.local.yaml`.
