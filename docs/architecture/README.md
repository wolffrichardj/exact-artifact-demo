# Why an archive hash is not enough

This local sample keeps two checks separate: **which archive was expected**, and **whether its exact files still match the independently expected manifest**. That separation makes the payload substitution observable even after the enclosing archive digest is deliberately re-pinned by the test constructor.

The diagram describes committed sample behavior at [`9173c2101daafcb131e62edecadd8da98cc98d8a`](https://github.com/wolffrichardj/exact-artifact-demo/tree/9173c2101daafcb131e62edecadd8da98cc98d8a). It ends at a local verdict. It does not describe a production release platform.

![Packaging and layered validation](preview.svg)

[Download the standalone interactive HTML](exact-artifact.html) · [Editable candidate](candidate.json)

## Read the boundary

`package()` owns the Git reads and output writes. It requires a clean Git root, captures the commit and tree, checks the exact `public/` inventory and regular-file mode, and reads the payload from the captured Git object rather than mutable working-tree bytes. It writes a deterministic tar/gzip archive and supplied-context evidence outside the source tree; a completion check rejects a dirty or moved source and removes its owned outputs on failure. [Source: `release.py:90–132`](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/release.py#L90-L132).

`validate()` owns candidate-file reads and the final verdict. Its caller supplies the expected repository/workflow, commit/tree, run/attempt, archive digest and manifest digest. A real caller must obtain these through an independent trusted path; the sample does not implement that acquisition. Copying expectations from untrusted evidence proves only self-consistency. [Source: `release.py:190–235`](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/release.py#L190-L235).

| Validation layer | What is actually checked |
| --- | --- |
| Outer bytes and supplied context | Exact archive name/digest; exact evidence fields, including push/main/success, compared with expected values. These strings do not authenticate CI. |
| Archive boundary | Compressed and expanded size at most 1 MiB; canonical paths and regular members only; no duplicates, links, extension records, hidden trailing members or missing entries. Inspected in memory without extraction. |
| Source metadata | `RELEASE.json` exactly matches format, captured commit/tree and clean state, with duplicate-key and type checks. |
| Manifest and payload | Independently expected manifest digest, strict rows, exact membership, and each payload/metadata digest. |

The exact archive inventory is `public/index.html`, `RELEASE.json`, and `MANIFEST.sha256`. The manifest covers the payload and release metadata, not itself. [`read_members():144–173`](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/release.py#L144-L173) and [`validate():219–235`](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/release.py#L219-L235) enforce these boundaries.

The CLI catches `ValueError` and `OSError`, writes rejected JSON to stderr, and exits 1. Packaging checks supplied context first (`EVIDENCE_MISMATCH`), then source/output policy (`SOURCE_INVALID`); filesystem errors can retain OS messages without a stable category prefix. Direct Python calls raise exceptions. Argument-parser errors are outside that handler. [CLI source](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/release.py#L238-L260).

## The failure that motivates the design

[`demo.py:9–31`](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/demo.py#L9-L31) first verifies a good package. The demo constructor then substitutes the page, rebuilds the archive, and re-pins only the outer digest in both evidence and expected input. The original manifest bytes and expected manifest digest remain. The outer check now passes; per-file checking rejects the substituted page with `PAYLOAD_HASH_MISMATCH`. This is a deliberate test setup, not an attacker capability granted by the validator.

The [fault-sensitivity test](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/tests/test_release.py#L68-L76) temporarily disables per-file comparison and confirms the corrupted fixture would be admitted. The adjacent [all-inputs-replaced test](https://github.com/wolffrichardj/exact-artifact-demo/blob/9173c2101daafcb131e62edecadd8da98cc98d8a/tests/test_release.py#L78-L80) proves the limit: control of the artifact, evidence and every expected input can forge agreement.

This repository provides no signatures, authenticated CI provenance, host activation, rollback, transport or production deployment. Its GitHub workflow runs tests and the local demo; supplied workflow context is not that workflow's attestation. The source adaptation and AI assistance remain described in the [root README](../../README.md#scope-and-lineage) and [NOTICE](../../NOTICE.md).

## Open, inspect and regenerate

GitHub displays HTML source or offers a download; it does not run this viewer as a hosted page. Download `exact-artifact.html` using **Download raw file**, then open that local file in a current desktop browser. It is standalone: no service, account or build step is needed to view it. Use the viewer's source links to inspect the pinned public code. `preview.svg` is the clean full-diagram static export used in the root README; it follows the host light/dark preference. A [PNG export](preview.png) is also available.

`candidate.json` is the editable diagram source. `hashes.json` records portable SHA-256 hashes of the reviewed candidate, HTML and previews plus their source revision. It is an integrity inventory, **not** an exact Archify strict-provenance receipt or a CI attestation. Exact host-specific delivery/browser/capture receipts are retained privately because they contain machine paths.

To regenerate, install [Archify](https://github.com/tt-a1i/archify) separately, set `ARCHIFY` to its package directory, and run the command below from the repository root. Node.js 18+ and a supported Chrome/Chromium/Edge browser are required for the complete gate. Regeneration writes fresh provenance and browser receipts for your machine. Keep those local. The source citations remain pinned to the revision named above; when behavior changes, inspect the new committed source and revise the candidate citations before regenerating.

```sh
node "$ARCHIFY/bin/archify.mjs" finalize workflow \
  docs/architecture/candidate.json docs/architecture/exact-artifact.html \
  --repo-root . --quality showcase --out-dir ../exact-architecture-checks --json
```

The checked-in HTML was generated using Archify 3.2; re-rendering with a different package revision can change viewer bytes without changing sample behavior. Export the full diagram as **SVG · Auto** and PNG from the finalized viewer's Export menu to refresh the README previews. Inspect the refreshed diagram in light and dark themes before replacing the portable hashes.

Architecture documentation was authored with AI assistance and checked against this public source revision. This adds no per-line human-authorship claim. The bundled viewer uses Archify under the [MIT license](ARCHIFY-LICENSE.txt) and embeds JetBrains Mono under the [SIL Open Font License](JetBrainsMono-OFL.txt). The sample's own [MIT license](../../LICENSE) remains unchanged.
