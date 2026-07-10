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

[On PyPI](https://pypi.org/project/folder-nature/) since 2026-07-05 — ahead of
the planned late-July date. Requires Python 3.10+. Single runtime dependency: PyYAML.

Latest development version:

```bash
pip install git+https://github.com/myfjin/folder-nature.git
```

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
5. **Open from day one.** Apache-2.0 from 0.2.0 onward (adds a patent grant
   covering the signing/watermark work; the `0.1.0` release remains MIT).
   Code reviewable. Schema documented.

## The mark layer (`v-next`) — attribution + authenticity, never prevention

The `v-next` branch adds the layer that lets a folder of work be *sold with
attribution*: a configurable trademark, an invisible-and-visible watermark, a
cooperative copy tool, leak tracing, and cryptographic file signing.

**The load-bearing truth, stated up front:** you **cannot** prevent someone
copying files on their own disk — `cp` beats any in-file mechanism, and we have
zero visibility into a customer's machine. Nothing here pretends otherwise.
What it *does* is make a copy **checkable**:

| Mechanism | The question it answers | What it is **not** |
|-----------|-------------------------|--------------------|
| **Watermark** | *Who* bought this copy? | Not copy protection |
| **Signature** | Is this *genuinely* ours and *unaltered*? | Not copy protection |
| **Copy-limiter** | Cooperative numbering for honest customers | Not anti-piracy |
| **Leak scan** | Trace a found copy → the buyer → their accepted license | Not surveillance of your disk |

### Watermark — three redundant channels

A mark is embedded across three channels with disjoint failure modes, so an
honest reformat can't silently strip it, and the file **still runs** after
stamping (guaranteed for Python by an in-process `compile()` before write):

- **zero-width** — invisible steganographic bits (survives every mainstream
  code formatter; killed only by an explicit "strip zero-width unicode" pass).
- **comment-id** — a visible attribution comment `△ folder-nature mark ⟦…⟧`
  (survives reformatting; killed by "remove all comments").
- **structural** — a real language constant, e.g. `_AURA_MARK = "…"` (survives
  comment-stripping *and* whitespace reformatting; killed by dead-code removal).

Extraction succeeds if **any one** channel yields a CRC-valid payload; a channel
present but CRC-broken, or channels that disagree, is reported as **tampered**.
The master original is number `0`; per-customer numbers are stamped **at sale**,
never at authoring (they encode the buyer). Tiers: `personal` 1–3 · `team` 0–9 ·
`enterprise` base36 ≥ 10.

### Signing — origin + integrity (distinct from the watermark)

`sign` hashes every file (sha256) into a manifest and signs it with **Ed25519**
(pure-Python, vendored, verified against the RFC 8032 test vectors — see
`tests/test_ed25519_vectors.py`). The private key is written mode `600` and is
**never** committed (the tool refuses to write a key inside a git repo). `verify`
checks the signature against a *trusted published* public key, then re-hashes the
tree and reports **"authentic + unaltered"** or names exactly what differs
(modified / missing / added). Origin + integrity — not prevention.

### The enforcement chain

A watermark has teeth only if a **license was accepted**. The chain is:
license presented → buyer accepts at purchase (recorded, with the license text
hashed) → the copy is watermarked to that buyer → if a leak is later *found*, the
scan traces the number to the buyer and emits a claim **citing the license they
accepted**. Leak claims fire on found content, **never** on a customer's local
copying. (License *texts* are a deliberate later decision; the mechanism ships
now with a clearly-flagged placeholder.)

```bash
folder-nature trademark ./lib --set "Your Mark" --tier team   # configurable name (no default)
folder-nature stamp ./lib --number 0                          # master watermark; files still run
folder-nature mark-show ./lib/file.py                         # extract + verify a mark
folder-nature keygen --out ~/.config/folder-nature/signing.key
folder-nature sign ./lib --key ~/.config/folder-nature/signing.key
folder-nature verify ./lib --pubkey ~/.config/folder-nature/signing.key.pub
folder-nature verify ./tree --root --pubkey <key>   # self-validate a WHOLE tree → one verdict
folder-nature scan ./suspect_dir --registry ~/private/sales.json   # trace + claim
```

### Root orchestration — a self-validating tree

`folder-nature verify <root> --root` turns a folder-nature tree into an
**orchestrator** that signs off with one GREEN/RED verdict only if *everything*
checks, top-down: **structure** (every `.folder-nature` schema-valid, tree matches
its declared layout, folder/file counts reported) · **folder marks** (every folder
carries a valid `.folder-mark.yaml`) · **file signatures + watermarks** (every
*file's* Ed25519 signature and watermark verifies — not just folders) · **parity**
(the signed manifest matches disk exactly — no added/missing/modified) · optional
**selftests** (`--selftest` runs a declared, deterministic per-file run-gate).

It discovers signed subtrees by finding `MANIFEST.aura` — nothing is hard-coded —
so any folder-nature root can self-validate. A tampered file, a missing signature,
catalog↔disk drift, an invalid tag, or a failing selftest each fails loudly and
names itself. Optional root declaration in `.folder-nature-root.yaml`. Honest
scope: this proves authenticity + integrity + structure — it does **not** prevent
copying.

## Roadmap

- **v0.1 (this release):** core MVP — schema, CLI, 5 templates, tests
- **v0.2:** export/import, migration tool, more templates
- **v1.0:** AI integration (`folder-nature ai-suggest`), filesystem watcher,
  comprehensive docs

## License

Apache-2.0 from 0.2.0 onward. See [LICENSE](LICENSE). (The `0.1.0` release
remains MIT.)

## Development

```bash
git clone https://github.com/myfjin/folder-nature
cd folder-nature
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Test suite: 66 core tests (schema validation, filesystem operations, search,
CLI integration) plus the `v-next` mark-layer suite — Ed25519 RFC-8032 vectors,
watermark gate-compatibility, reformat survival (including a real `black` run),
extractability, tamper detection, copy-limiter tiers, sign/verify round-trip and
tamper-fails-verify, and the sale→leak→claim enforcement chain.

## Origin

folder-nature emerged from internal infrastructure work in early 2026 —
a working hypothesis that filesystems become more useful when directories
carry semantic identity. The concept proved itself on a 3-node operational
mesh before being extracted as this standalone tool.

🐍🦅💎
