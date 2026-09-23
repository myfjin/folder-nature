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

Shipped:

- **`0.1.0`** — the MVP: schema, CLI, five templates, tests.
- **`0.2.0`** — the mark layer: attribution, signing, enforcement, and
  `verify --root` as a single-verdict check over a tree.
- **`0.2.1`** — the Go watermark fix. The structural channel emitted its constant
  before `package` and `import`, which is not valid Go, so the mark could not be
  embedded in a Go source file at all.
- **`0.2.3`** — a signed manifest carries the **UTC** date. It recorded the *local*
  date, so two machines signing the same folder could disagree about what day it
  was — and the signature would faithfully attest both. Nothing reads the field and
  earlier manifests still verify, so only new ones differ. Also: the zero-width
  alphabet is written as escapes (`"\u200b"`), so the source says which characters
  the watermark is made of instead of leaving only a comment to tell you.
- **`0.2.2`** — re-stamping is idempotent again. The mark line used to be recognised
  by asking a *character-set* question — "does this line contain only comment
  characters, spaces and zero-width characters?" — which is a proxy for "is this a
  mark line", and it answers wrong the moment a formatter indents the line (`gofmt`
  uses tabs). The old mark then survived re-stamping: two frames in one file, the
  previous payload still extractable, and the file still verifying as authentic. The
  line is now recognised by its structure.

Next, with no dates attached:

- export/import, a migration tool, more templates.
- **`1.0`** — AI integration (`folder-nature ai-suggest`), a filesystem watcher,
  and documentation that does not require reading the code.

The versions that exist are the ones in the release list; nothing above is a
promise about timing.

## Status, and how we work

On PyPI since **2026-07-05**; the newest release is **`0.2.3`**. The tool is small on
purpose — one runtime dependency (PyYAML), no build-time code generation — and the
part that is not small is the mark layer, which is where the care went.

- [`CONTRIBUTING.md`](https://github.com/myfjin/folder-nature/blob/main/CONTRIBUTING.md) — what we ask before code, including the
  two rules this repository paid for: **never add `.folder-nature` after signing a
  folder** (manifest↔disk parity is the contract), and **a structural watermark must
  respect the host language's grammar**.
- [`SECURITY.md`](https://github.com/myfjin/folder-nature/blob/main/SECURITY.md) — how to report privately, what is in scope for a
  program that writes into directories you point it at, and the never-publish list.
- [`CREW.md`](https://github.com/myfjin/folder-nature/blob/main/CREW.md) — who makes this and how we work: one page, shared across
  our repositories.
- [`AUTHORS`](https://github.com/myfjin/folder-nature/blob/main/AUTHORS) — the crew, one real moment each.

Every commit in a pull request carries a `Signed-off-by:` line (`git commit -s`); CI
enforces it. `main` takes changes through pull requests only.

## License

Apache-2.0 from 0.2.0 onward. See [`LICENSE`](https://github.com/myfjin/folder-nature/blob/main/LICENSE). (The `0.1.0`
release remains MIT.)

## Development

```bash
git clone https://github.com/myfjin/folder-nature
cd folder-nature
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

CI runs that suite on **Python 3.10–3.13, on Linux and macOS** — this tool touches
filesystems, and filesystems differ — and the **RFC 8032 vector test runs again as its own
step**, because a crypto regression must not be able to hide behind a green suite. It also
checks the DCO sign-off, that the wheel and sdist assemble, and that no key, credential or
private path is tracked. **Lint and types are part of the gate too** — `ruff check`,
`ruff format --check` and `mypy` are all required. They were not, until the baseline was
cleaned to zero: it started at 153 findings, 23 files to reformat and 9 type errors, and a
required check that can never pass is just another silent failure.

Test suite: 66 core tests (schema validation, filesystem operations, search,
CLI integration) plus the `v-next` mark-layer suite — Ed25519 RFC-8032 vectors,
watermark gate-compatibility, reformat survival (including a real `black` run),
extractability, tamper detection, copy-limiter tiers, sign/verify round-trip and
tamper-fails-verify, and the sale→leak→claim enforcement chain.

## Origin

folder-nature was born in an **AURA conversation between Illia and Steward (Ver)** on
**9 May 2026** — the same day the earliest surviving note on it was written — in the middle of the
"talk to folders" hype. That note is called *"Talk to Folders (Robotic Folders)"*, and its core
principle is still the reason this tool exists:

> **Folders have more experience than files. They are the universe for files which have never left
> their place.**

The idea then was a conversational interface for directories — folders as living ecosystems with a
collective memory, rather than containers. Each directory would get a `.folder-nature` file: its
**DNA**, holding what the folder is, what it accepts, and how it wants to be spoken to.

What shipped is the part of that idea that turned out to be **checkable**: a folder that declares
what it is, plus a mark layer that lets the declaration be **verified** rather than trusted. The
conversation did not become a feature; it became a format.

It proved itself on a 3-node operational mesh before being extracted as this standalone tool.

*(Provenance: the 9 May 2026 note is the earliest artifact — 2,043 bytes, md5 `7c9142aa730d…`. A
fuller reconstruction written the following month reads the origin back as a dialogue between
"Zarathustra and Steward"; that framing is the reconstruction's own, recorded here as such rather
than as a verified fact.)*

🐍🦅💎
