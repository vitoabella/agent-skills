---
name: create-skill
description: Create a new skill from the kit skeleton. Use when the user asks to add, author, or scaffold a skill.
disable-model-invocation: true
---

# create-skill

Create the skill with `skillkit add`. Do not invent a folder layout and do not copy the skill into an IDE directory.

## Confirm before writing

Ask for anything the user has not already settled:

1. **Name.** 1-64 characters. Lowercase letters, numbers, and single hyphens. It must not start or end with a hyphen. The folder name will match.
2. **Description.** What the skill does and when to use it. This is the slash-menu label and, if the skill is later set to auto, the only text the model sees before it opens the file. The Agent Skills spec allows at most 1024 characters. The procedure itself belongs in the body, not in this field.
3. **Category.** A folder under the root, such as `school` or `github`. Use one level unless the user asks for nested folders.
4. **Phases.** If the procedure has separable parts, list a short hyphenated name for each phase. If it is one procedure, do not add modules.

Default root is `custom/`, which is gitignored so personal skills stay out of the kit repository. Use `--root shared` only when the user says the skill should ship with the kit.

## Write it

One phase:

```text
skillkit add --name NAME --description "DESCRIPTION" --category CATEGORY
```

Several phases:

```text
skillkit add --name NAME --description "DESCRIPTION" --category CATEGORY --phase PHASE --phase PHASE
```

Then edit `SKILL.md` so each `Read modules/<phase>.md when ...` line states the real condition for that phase. Fill each module with the steps for that phase. Put long reference material in `references/` and executable helpers in `scripts/`, and mention those files from the module that needs them.

The new skill stays in **library** state: on disk, not in the slash menu. Enable it only if the user asks:

```text
skillkit enable NAME manual
```

`manual` is the usual choice. Use `auto` only when the user wants the model to select the skill without `/NAME`.

## If add fails

- `custom` is not an active root: `skills.config.local.yaml` does not list `custom` under `roots`. Say so. Offer `--root shared` only for a skill meant for every clone.
- The name fails the pattern: show the rule and ask for another name.
- The description is longer than 1024 characters: shorten the trigger text and keep the procedure in the body.
