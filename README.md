# Skill kit

Skills live in this repository. Cursor, Claude Code, GitHub Copilot, and Antigravity only get links, so `/name` shows up in each IDE and the files stay here.

```text
agent-skills/
├── README.md                 # install and how the kit works
├── pyproject.toml            # pip install
├── skills.config.yaml        # defaults, and which skills are linked
├── skills.config.local.yaml  # your machine only, not in git
├── meta/
│   ├── library/SKILL.md      # /library
│   └── create-skill/SKILL.md # /create-skill
├── shared/                   # skills published with this repo
├── custom/                   # your skills, gitignored
├── templates/skill/SKILL.md  # copied by skillkit add
└── skillkit/                 # the skillkit command
```

## Install

```text
git clone <repository-url>
cd agent-skills
pip install -e .
skillkit install --workspace "<path-to-a-project>"
```

Open that project and type `/library`. A project you have not installed into has no slash commands from this kit. Run `skillkit install --workspace` again to point at another project.

The install adds junctions named `library` and `create-skill`. It does not move or delete skill folders that are already real directories. If a folder with one of those names already exists and is not a link, install stops and leaves it alone.

## Your skills

`custom/` is listed in `.gitignore`, so personal skills are never part of this repository. Tell the kit to use it by creating `skills.config.local.yaml`:

```yaml
roots:
  - meta
  - shared
  - custom
```

`skillkit add` writes there and creates `custom/` if needed. To keep those skills in git, initialize a separate private repository inside `custom/` and push that on its own. Push this kit only when `meta/`, `shared/`, or the tooling changes.

## Commands

Edit skills in this repo. IDE folders are junctions back to these files.

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
```

`find` prints a few paths and descriptions. It does not print skill bodies. The first `find` builds `catalog/index.yaml`, which is gitignored.

`add` leaves the skill unlinked. `enable NAME manual` adds `/NAME`. `auto` lets the IDE select the skill from its description. `disable` takes it off the menu and leaves the files.

`reset` copies `defaults` onto `settings` in `skills.config.yaml` and relinks. It does not change `skills.config.local.yaml` or `custom/`.

Pass `--root shared` to `add` or `move` when the skill should ship with the kit. `shared/` is created the first time you do that.

## States

Stored under `settings.skills` in `skills.config.yaml`. A missing name means library.

- **library** — on disk only. `skillkit find` can see it. It is not in the slash menu.
- **manual** — linked, so `/name` autocompletes. The model reads the skill when you call it. This is the usual choice, and it keeps the skill body out of the prompt until you call it.
- **auto** — linked, and the IDE may open it when the description matches the task. Each auto skill's name and description are sent on every turn.

`description` is required and at most 1024 characters. It labels the slash menu. For an auto skill it is also the only text the model sees before it opens the file, so say what the skill does and when to use it. The steps belong in the body.

## Modules

Optional. Use them when one skill has separate phases, so the agent reads one part instead of the whole procedure. `SKILL.md` says when to read each file. The category is the folder name, such as `school` in `custom/school/lecture-notes/`.

```text
skillkit add --name deploy-app --description "Deploy the app. Use when shipping." --category shipping --root shared --phase staging --phase production
```

## Where the links go

`skillkit install` does not copy skill files.

In a project it links each manual and auto skill into:

- `<project>/.claude/skills/<name>` — Claude Code, Cursor, and Copilot
- `<project>/.agents/skills/<name>` — Antigravity; Cursor and Copilot also read this

Cursor and Copilot may list the command twice. That is how `/name` exists in all four IDEs. `skillkit doctor` reports it.

Those links are gitignored in the project, along with `.skillkit-managed`, which is the list install is allowed to remove. Do not install into this kit repo.

For every project on the machine, set `scope: user` under `settings` and install. Links then go to `~/.claude/skills`, `~/.gemini/config/skills`, and `~/.copilot/skills`.