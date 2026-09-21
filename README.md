# Skill kit

## Introduction

This repository is a library of [Agent Skills](https://agentskills.io/specification). A skill is a folder with a `SKILL.md` file: a short description, plus the steps an agent should follow.

It is for Cursor, Claude Code, GitHub Copilot, and Antigravity. You write each skill once, in this repo. The `skillkit` command links that folder into the IDE, so `/name` shows up in the project you are working in.

That keeps one copy of every skill. The catalog can search it. Each skill has a state: on disk only, available as a slash command, or offered by the IDE when the description matches the task.

## Layout

```text
agent-skills/
├── README.md                         # this guide
├── pyproject.toml                    # package metadata; pip install -e . installs the skillkit command
├── skills.config.yaml                # defaults (what reset restores) and settings (scope, roots, which skills are linked)
├── skills.config.local.yaml          # this computer only: project path and extra roots such as custom/. Git ignores it.
├── .gitignore                        # keeps personal skills, the local config, and the search catalog out of git
├── meta/                             # skills that operate the kit. They ship with the repository.
│   ├── library/SKILL.md              # /library — find, enable, move, install, and reset through the agent
│   └── create-skill/SKILL.md         # /create-skill — collect the details and scaffold a new skill
├── shared/                           # skills published for every clone. Created the first time you add one here.
├── custom/                           # your own skills. Git ignores this folder. A private repo can live inside it.
├── templates/
│   └── skill/SKILL.md                # skeleton that skillkit add copies. Edit it to change every new skill.
├── catalog/                          # search index built by skillkit find and skillkit index. Git ignores it.
│   ├── index.yaml                    # names and descriptions from meta/ and shared/
│   └── index.local.yaml              # names and descriptions from custom/. Written when those skills exist.
└── skillkit/                         # the skillkit command
    ├── __init__.py                   # package version
    ├── __main__.py                   # python -m skillkit
    ├── cli.py                        # subcommands: add, find, enable, install, and the rest
    ├── config.py                     # load, overlay, and save the two YAML config files
    ├── skills.py                     # discover skills, check the Agent Skills rules, add, move, and remove
    ├── install.py                    # create and remove IDE links (junctions on Windows, symlinks elsewhere)
    └── index.py                      # build catalog/ and answer skillkit find
```

## Getting started

### Install

You need Python 3.11 or newer.

```text
git clone https://github.com/vitoabella/agent-skills.git
cd agent-skills
pip install -e .
skillkit install --workspace "<path-to-a-project>"
```

Open that project. `/library` and `/create-skill` appear in the slash menu.

Install remembers the project in `skills.config.local.yaml`. Later you can run `skillkit install` with no path. Pass `--workspace` again when you want the same skills in another project.

Install links each enabled skill. On Windows the link is a junction. On macOS and Linux it is a symlink. If a real folder already sits at that path, install stops and leaves the folder as it is.

Links go to:

- `<project>/.claude/skills/<name>` — Claude Code, Cursor, and Copilot
- `<project>/.agents/skills/<name>` — Antigravity. Cursor and Copilot also read this folder.

Cursor and Copilot can list each command twice, because they read both folders. `skillkit doctor` reports that.

Install also gitignores those links in the project, along with `.skillkit-managed`, the list of links this kit is allowed to remove. Point `--workspace` at a project you write code in. Install refuses the kit repository itself.

### Use the kit

#### Create a new skill

Personal skills go in `custom/`, which git ignores. Turn that folder on once. Create `skills.config.local.yaml` in the kit repo:

```yaml
roots:
  - meta
  - shared
  - custom
```

In the IDE, run `/create-skill`. It asks for the name, description, and category, then writes the skill.

From the terminal, the same step is:

```text
skillkit add --name lecture-notes --description "Turn a lecture into notes. Use when the user shares lecture material." --category school
```

The name is 1–64 characters: lowercase letters, numbers, and single hyphens, and it matches the folder. The description says what the skill does and when to use it, in at most 1024 characters. The steps belong in the body.

That command writes `custom/school/lecture-notes/SKILL.md` from the template and leaves the skill off the slash menu. Edit the file, then:

```text
skillkit enable lecture-notes manual
```

`manual` adds `/lecture-notes`. The model reads the skill when you call it.

A skill with separate phases gets one file per phase:

```text
skillkit add --name deploy-app --description "Deploy the app. Use when shipping." --category shipping --phase staging --phase production
```

`SKILL.md` tells the agent when to open each file in `modules/`. Long reference material goes in `references/`. Helpers go in `scripts/`. Mention those files from the skill or the module that needs them.

#### Bring in skills you already have

Copy each existing skill folder into `custom/<category>/<name>/`, including `scripts/`, `references/`, and `modules/` when they are part of the skill. The folder name is the skill name, and `SKILL.md` sits inside it:

```text
custom/school/lecture-notes/SKILL.md
```

Before you enable it:

- `name` in the frontmatter matches the folder.
- `description` is present and at most 1024 characters.
- Every file in `modules/` is named from `SKILL.md`, and every `modules/...` path in `SKILL.md` exists.
- `custom` is listed under `roots` in `skills.config.local.yaml`, as in the section above.

Then check the skill and link it:

```text
skillkit validate
skillkit enable lecture-notes manual
skillkit install
```

`validate` checks names, descriptions, and module paths. `enable` records the slash command and refreshes IDE links when a project is already saved. `install` creates the links if you have not installed yet.

### Maintain the library

Edit skills in this repository. The IDE folders are links back to these files.

**From the terminal**

```text
skillkit find QUERY
skillkit add --name NAME --description "WHAT AND WHEN" --category CATEGORY
skillkit enable NAME manual
skillkit enable NAME auto
skillkit disable NAME
skillkit remove NAME
skillkit move NAME --category CATEGORY
skillkit install --workspace PATH
skillkit reset
skillkit doctor
skillkit validate
```

| Command | What it does |
| --- | --- |
| `find` | Prints a few matching paths and descriptions. The first run builds `catalog/`. |
| `add` | Creates a skill and leaves it off the slash menu. |
| `enable NAME manual` | Adds `/NAME`. The model reads it when you call it. |
| `enable NAME auto` | Adds `/NAME` and lets the IDE open it when the description matches the task. The name and description are sent on every turn. |
| `disable` | Takes it off the slash menu. The files stay on disk. |
| `remove` | Deletes the skill folder and its IDE links. |
| `move` | Changes the category. Add `--root shared` or `--root custom` to change which tree it lives in. |
| `install` | Refreshes IDE links for every manual and auto skill. |
| `reset` | Copies `defaults` onto `settings` in `skills.config.yaml` and relinks. `skills.config.local.yaml` and `custom/` stay as they are. |
| `doctor` | Checks links, the custom root, and the catalog. |
| `validate` | Checks skill files against the Agent Skills rules. |

A skill with no entry under `settings.skills` is in the library: on disk, visible to `skillkit find`, and absent from the slash menu. New skills stay there until you enable them.

**From the IDE**

After install, two skills maintain the kit:

- `/library` finds skills, enables and disables them, moves and removes them, installs links, and resets settings. It runs `skillkit` for you.
- `/create-skill` scaffolds a new skill in `custom/` and leaves it unlinked until you ask to enable it.

## Customization options for power users

**Config files.** `skills.config.yaml` holds `defaults` and `settings`. `defaults` is what `skillkit reset` restores. `settings` is what the kit uses: `scope`, `roots`, and a map of skill name to state.

`skills.config.local.yaml` is for this machine, and git ignores it. A key here replaces the same key from `settings`. Install writes `workspace` into this file. When you add a root, list the full set:

```yaml
workspace: C:\path\to\your\project
roots:
  - meta
  - shared
  - custom
```

`meta` and `shared` are always included, even if this list omits them.

**Scope.** `workspace` is the default. Links go into one project, as described under Install. Set `scope: user` under `settings` to link every project on the machine:

- `~/.claude/skills`
- `~/.gemini/config/skills`
- `~/.copilot/skills`

Then run `skillkit install`.

**States.** Stored under `settings.skills`.

- **library** — on disk, searchable, off the slash menu.
- **manual** — linked as `/name`. This is the usual choice. The file gets `disable-model-invocation: true`, so the body stays out of the prompt until you call the skill.
- **auto** — linked, and the IDE may open it from the description alone. Each auto skill's name and description go out on every turn.

**Description.** Required, at most 1024 characters. It labels the slash menu. For an auto skill it is also the only text the model sees before it opens the file, so say what the skill does and when to use it.

**Roots.** `meta/` ships the kit skills. `shared/` ships skills you want in every clone. Pass `--root shared` to `add` or `move` for those. `custom/` is yours. To keep personal skills in git, initialize a separate private repository inside `custom/` and push that on its own.

**Template.** `templates/skill/SKILL.md` is what `skillkit add` copies. The placeholders are `{{name}}`, `{{description}}`, and `{{instructions}}`.

**Where the command looks.** After `pip install -e .`, `skillkit` finds this repo from the installed package. Set `SKILLKIT_ROOT` to the repo path when you need to point at a specific clone.

**Catalog.** `skillkit index` rebuilds `catalog/`. `skillkit find` reads that index and prints paths and descriptions. `skillkit doctor` warns when a skill is missing from it.

## Contributing

Issues and pull requests are welcome on [github.com/vitoabella/agent-skills](https://github.com/vitoabella/agent-skills).

1. Fork the repository and create a branch.
2. Put a skill that should ship with the kit in `shared/` (`skillkit add --root shared`). Put command changes in `skillkit/`.
3. Run `skillkit validate`.
4. Open a pull request that says what changed and why.

Leave `custom/`, `skills.config.local.yaml`, and `catalog/` untracked. They are personal or generated. Push this repository when `meta/`, `shared/`, or the tooling changes.

## Credits

### Buy me a coffee

If this kit saves you time, feel free to send me a thank you :)

### A note from me

I'm Vito. I wanted one place to write agent skills, and `/name` in whichever IDE I opened that day. This repository is that place: the files stay here, and the editors get links. Thanks for using it.
