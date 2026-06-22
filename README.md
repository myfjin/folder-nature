# folder-nature

> *Folders are not containers. They're ecosystems with collective memory, personality, and rules.*

A directory becomes a conversation partner: it has identity, purpose, rules,
and history, all captured in a hidden `.folder-nature` YAML file at the
directory's root.

## What problem this solves

Filesystems don't carry meaning. `~/Projects/old_v3_final/` could be anything.
Search-by-filename doesn't help when you can't remember the filename. New team
members start from zero. AI assistants scan everything.

folder-nature attaches a small piece of YAML to each directory that captures:
- What this folder is for
- What kind of folder it is (workspace, archive, configs, ...)
- What tags apply
- What rules govern it
- When it was created and what notable things happened

Once attached, you can search by meaning, walk up to find the boss folder,
validate the tree, and let AI tools query a folder's intent before they
interact with its contents.

## Install

```bash
pip install folder-nature
```

Requires Python 3.10+. Single runtime dependency: PyYAML.

## 5-minute tour

```bash
# Create something to tag
mkdir demo && cd demo
mkdir -p Old_Stuff RANDOM new_new_final download untitled_folder

# Tag the root
folder-nature init . --template workspace --name "demo-workspace"

# Show what got created
folder-nature show .

# Reorganize + tag the new structure
mkdir -p projects/{active,archive} clients/{acme,startup-x} documents
folder-nature init projects/active --template workspace
folder-nature init projects/archive --template archive
folder-nature init clients --template client-project --name "my-clients"
folder-nature init documents --template documentation

# Search by meaning
folder-nature search . --tag client
folder-nature search . --being collector

# Validate the tree
folder-nature validate .

# Tree view
folder-nature list .
```

## Templates (`init --template`)

Five archetypes ship with the package:

| Template | When to use |
|----------|-------------|
| `workspace` | Active project working directory |
| `client-project` | Client-specific work folder |
| `archive` | Historical / inactive storage |
| `deployment` | Production-touching configs and scripts |
| `documentation` | Docs, references, guides |

Customize at init time with `--name "your-name"` or edit the resulting
`.folder-nature` file directly afterward.

## Commands

| Command | What it does |
|---------|--------------|
| `folder-nature init [PATH] [--template T]` | Create a new `.folder-nature` |
| `folder-nature show [PATH]` | Print closest `.folder-nature` (walks up) |
| `folder-nature query [PATH]` | Find the `director: true` ancestor |
| `folder-nature search [ROOT] [--tag T] [--being B] [--name N]` | Filter folders by criteria |
| `folder-nature validate [ROOT]` | Schema-check all `.folder-nature` files in tree |
| `folder-nature list [ROOT]` | Tree view of every tagged folder |
| `folder-nature version` | Print tool + schema versions |

`PATH` and `ROOT` default to the current directory.

## Schema v1.0

A `.folder-nature` file is YAML with this shape:

```yaml
schema_version: "1.0"             # REQUIRED

identity:                         # REQUIRED
  name: "Projects"
  being: "director"
  purpose: "Canonical root for all work"

director: true                    # OPTIONAL (default false)

tags:                             # OPTIONAL
  - work
  - canonical
  - active

rules:                            # OPTIONAL
  - "Only deployed code lives here"

memory:                           # OPTIONAL
  created: "2026-05-09"
  last_significant_change: "2026-06-22"
  notable_events:
    - "2026-05-09: initial setup"
```

The `identity.being` field accepts a controlled vocabulary plus arbitrary
custom values (extensibility hatch). Known types:

`director` · `collector` · `workspace` · `assets` · `configs` ·
`documentation` · `ideas` · `external` · `legal` · `team-shared` ·
`private` · `system`

## Design principles

1. **Files, not databases.** Each folder owns its own YAML. Git-friendly,
   editor-friendly, no central store.
2. **Self-hosted.** Runs entirely local. No network calls. No telemetry.
3. **Schema-versioned.** Future schema bumps migrate cleanly.
4. **AI-readable.** Optional integration with LLM assistants — they query the
   folder's nature before interacting with its contents.
5. **Open from day one.** MIT licensed. Code reviewable. Schema documented.

## Roadmap

- **v0.1 (this release):** core MVP — schema, CLI, 5 templates, tests
- **v0.2:** export/import, migration tool, more templates
- **v1.0:** AI integration (`folder-nature ai-suggest`), filesystem watcher,
  comprehensive docs

## License

MIT. See [LICENSE](LICENSE).

## Development

```bash
git clone https://github.com/myfjin/folder-nature
cd folder-nature
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Test suite: 66 tests covering schema validation, filesystem operations,
search, and CLI integration. Should run in <1 second.

## Origin

folder-nature emerged from internal infrastructure work in early 2026 —
a working hypothesis that filesystems become more useful when directories
carry semantic identity. The concept proved itself on a 3-node operational
mesh before being extracted as this standalone tool.

🐍🦅💎
