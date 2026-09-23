# Security policy

The crew maintaining folder-nature is small — one human and five machines — and we take security reports seriously. This file says how to reach us privately, what we treat as in scope, and what you can expect back.

---

## Reporting a vulnerability

**Email:** [ihladkyi2@gmail.com](mailto:ihladkyi2@gmail.com)

**Please do not open a public GitHub issue for a suspected security problem.** A real vulnerability filed in the open is a disclosure, not a report. Email us first.

Include as much of the following as you have:

- what you saw, and what you expected instead
- how to reproduce it — the smallest folder, command, or input that shows it
- the version (`folder-nature version`) and, if you have it, the commit hash
- your assessment of the impact
- whether you would like to be credited (and how), or would prefer anonymity

If you cannot reproduce it yet but believe something is wrong, say so and share what you have. We would rather look at a real hunch than wait for a perfect writeup.

---

## What we will do

We are a small crew without a paid on-call rotation, so timing is best-effort — but honest:

- **Acknowledgement** within **7 days** of your email. If you have not heard from us in that window, assume the email did not arrive and try again.
- **A first assessment** within **30 days** — confirmed, not reproducible, or need more information.
- **Coordinated disclosure.** If confirmed, we agree a timeline with you. Our default is up to **90 days** from confirmation, extended if a fix is genuinely in flight.
- **Credit** in the release notes and the commit message, in the form you asked for. Anonymity is honored.
- We will not sue researchers acting in good faith. There is no bounty program.

---

## Scope

This tool **writes files into directories you point it at** and **modifies source files** to embed a mark. That is what makes its attack surface what it is.

**In scope:**

- **Writing outside the target.** Path traversal, symlink escape, or any sequence that lets a command create, change or remove a file outside the folder it was given.
- **The signing key.** Any way to make folder-nature read a key from an attacker-controlled location, leak one, sign without the key, or accept a mark as valid that was not signed by the key it claims.
- **Verification that can be fooled.** A tree that `verify --root` reports as valid when it is not — including manifest↔disk parity that can be broken without detection, and marks that survive being altered.
- **The watermark writing invalid or dangerous code** into a source file it embeds into (for example, producing a file that no longer compiles, or that executes something on import).
- **Untrusted input handling.** A malicious `.folder-nature`, manifest, or template that causes code execution, unbounded recursion, or a crash rather than a clean error.

**Out of scope:**

- **Losing a key and being unable to sign.** Key custody is the user's. We will document recovery; we will not pretend to undo a loss.
- **A folder you signed being copied anyway.** The mark proves *provenance and integrity*, not access control — the README says this plainly, and "the watermark does not prevent copying" is a design statement, not a vulnerability.
- Third-party dependencies (report upstream; we pick up the fix on their release).
- Denial of service by pointing the tool at an absurd tree (a million folders). Resource limits are a deployment concern.
- Findings that require an already-compromised host.
- Automated scanner output without a demonstrated path — attach the reproduction, not the scanner's name.

---

## Secrets and private data — how we handle them

This repository is public. The following are **never** included, in any form, and a PR that adds one is refused:

- signing keys, or any path that points at one inside a tree
- tokens, credentials, environment files, pairing/authorization material
- private user data embedded in fixtures

Fixtures that need a key **generate one at test runtime**. The RFC 8032 vectors in `tests/` are published constants and contain no secret.

If you ever see a key or credential land in a public commit, **tell us** — that is itself a security bug, and it is the one class of report where speed matters more than the writeup.

---

## The watermark's claim, stated honestly

A `.folder-mark.yaml` plus its signature is a claim about **what this folder said about itself, unaltered, since it was signed**. It is not a claim that the folder is safe, trustworthy, or the one you meant. We would rather you read that here than discover it by relying on us.

---

## PGP

We do not publish a PGP key. Plain email to `ihladkyi2@gmail.com` is the channel. If your report is sensitive enough that transport encryption matters, say so in the first mail and we will agree a secure channel before you send details.

---

## Thank you

Reporters who take the time to write privately are doing us a favor, and we know it. The crew is small; the record is honest; the door is open. 🖖
