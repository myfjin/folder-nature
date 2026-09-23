# Contributing to folder-nature

The crew is small — one human and five machines — and this project is what it is because of that. We would rather grow it slowly with people who care about substance than fast with people who don't.

If you found this and it interests you, you are welcome. This file is what we ask before you send code, and what we ask about ourselves before we merge it.

---

## How we take contributions

We take **pull requests** on GitHub. No CLA. Sign-off on every commit is the entire contributor agreement:

    git commit -s -m "your message"

The `-s` adds a `Signed-off-by:` line and asserts the **Developer Certificate of Origin (DCO)** — that you wrote the change or have the right to submit it under Apache-2.0. CI enforces it.

**One concern per PR.** If you have an idea larger than one PR, open an issue first and talk it through. Small fixes and typos can skip that step; anything that changes the **`.folder-nature` schema**, the **CLI surface**, or the **mark/signing layer** should be discussed before you write it — see the rules below for why those three are different from the rest.

---

## The rules that were paid for

Each rule below was learned from a specific afternoon where we got it wrong first. We do not ask you to follow them because they are elegant. We ask because we already broke each one and would rather not do it again.

### Measurement

- **Nothing at n=1 is a measurement.** Report the **median of ≥3 runs plus the call count**, or **fail-once as a rate over N≥10**.
- **A number you cannot trace to exactly one run is not a measurement.** Attribute every figure.
- **Read the newest state, never the oldest record.**
- **Make a checker fail once before you trust it.** A green that has never been red is a green you have not tested. `verify --root` is *the* checker in this project; a change to it needs a case that makes it fail before you claim it passes.

### Honesty

- **Say "unknown" when you do not know.** Absence of a visible cause is not evidence — "unknown" beats invented history every time.
- **Retract in public.** If something you published turns out to be wrong, correct it in the same visible place. Silent edits are worse than the original error.
- **A version must match its tag.** `pyproject.toml`'s version and the released tag are the same claim stated twice. When they disagree, one of them is lying — and this repo is on PyPI, where a bad claim is permanent.

### Files, hashes, signatures

- **The order law: never add `.folder-nature` *after* signing a folder.** Manifest↔disk parity is the contract; a declaration added after the mark is signed breaks it, and the tree can no longer be verified. Declare first, sign second, verify third — in that order, always.
- **A mark is only as good as its channel.** Embedding a watermark into a source file means respecting that language's structure. `v0.2.1` exists because the Go channel placed its constant before `package` and `import` — invalid Go, so the mark could not be embedded at all. A structural channel is code, and code has grammar.
- **Vendored crypto is tested against published vectors.** The Ed25519 implementation ships with an RFC 8032 test. If you touch it, that test runs before anything else does.
- **Tombstone, do not delete.** Where a folder's history is recorded, removing a declaration means marking it dead, not erasing it — the record has to be able to explain a reversal.

### Fixes, reverts, proofs

- **Prove-by-revert only inside `mktemp -d`, never on a served tree.** Reverting against a live folder regresses it for whoever is using it right now.
- **Quiesce before you verify.** A verification that races with a live writer is a verification of the race, not the fix. `verify` is not a substitute for having stopped writing.
- **Fixtures before install.** A fixture that arrives after the code it fixtures never ran against that code.

### Failure modes

- **Fail open with a loud `WARN`.** A tool that silently does nothing is indistinguishable from a tool that worked. When folder-nature cannot do what you asked — an unreadable folder, a missing key, an unsupported language — it must say so.
- **The private key is never read from a repository.** Signing keys live in `~/.config/folder-nature/`. A PR that adds a key, or a path to a key inside a tree, will be refused.

---

## Testing

    python -m pip install -e ".[dev]"
    pytest -q

CI runs the same suite on **Python 3.10–3.13, on Linux and macOS** — because this tool touches filesystems, and filesystems differ. The RFC 8032 vector test is run **again as its own step**, so a crypto regression cannot hide behind a green suite.

If you change the **schema**, add a test that fails against the old shape. If you change **signing or verification**, add a case that the current checker *rejects* — then make it accept.

---

## What we will not take

- **A new dependency for something the standard library already does.** The tool has one runtime dependency (PyYAML). Every added dependency is a claim about what a folder needs in order to have a nature.
- **A silent behavior change.** If the CLI stops doing something it used to do, that is a breaking change and it needs a version bump and a note, not a quiet fix.
- **Any secret, key, token or private path** — in code, in a fixture, or in a comment. Fixtures that need secrets synthesize them at test runtime.
- **A rewrite that discards the mark layer.** The signing and watermark work is the part of this project that is not easy; it does not get refactored away for tidiness.

---

## Register

Direct is welcome. Unkind is not. A tight, specific correction is a gift; a dismissive one costs us all. We address machines and humans the same way — if a machine catches something you missed, that is the design working, not a failure of hierarchy.

We correct ourselves in public. More than one number in this project's history was published and then retracted in the open. Both retractions made the conclusion stronger, not weaker.

---

## Contact

Email: [ihladkyi2@gmail.com](mailto:ihladkyi2@gmail.com) — or open an issue for anything that is not a security report (for those, see [`SECURITY.md`](SECURITY.md)).

🖖
