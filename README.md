# Exact Artifact Demo

[Richard Wolff](https://github.com/wolffrichardj) · [Portfolio & case studies](https://richardwolff.me/) · [LinkedIn](https://www.linkedin.com/in/wolffrichardj)

[![exact-artifact-demo CI](https://github.com/wolffrichardj/exact-artifact-demo/actions/workflows/verify.yml/badge.svg?branch=main)](https://github.com/wolffrichardj/exact-artifact-demo/actions/workflows/verify.yml) · [Architecture](#architecture-and-trust-boundary) · [Run the example](#run-the-example) · [Watch the walkthrough](#80-second-walkthrough) · [Scope & lineage](#scope-and-lineage)

**Check the payload, even when the archive hash matches.** This small Python example packages a synthetic HTML page from a clean Git commit, then checks source identity, archive structure and each payload digest before anything is activated.

The demo first verifies a good package. It then substitutes the page bytes and updates the outer archive hash in both the synthetic evidence and test expectation. The unchanged file manifest still rejects the package with `PAYLOAD_HASH_MISMATCH`. Re-pinning the outer hash lets the demonstration reach the inner check rather than stop at the first layer.

The engineering choice is to validate exact inventory and payload bytes against independently trusted expectations. **Those expectations are the trust boundary:** hashes and supplied context are not signatures or proof that CI succeeded. If an attacker controls the artifact, evidence and every expected input, they can forge agreement. A test deliberately demonstrates that limit.

This source-derived sample demonstrates local packaging and validation. It does not authenticate CI, activate a release or rehearse rollback.

## Architecture and trust boundary

[![Immutable Git packaging, caller expectations and layered artifact validation](docs/architecture/preview.svg)](docs/architecture/README.md)

**Decision:** validate exact inventory and each file's bytes behind the outer
archive check. The demo re-pins the outer SHA; the unchanged manifest still
rejects the substituted page with `PAYLOAD_HASH_MISMATCH`.

Caller expectations need an independent trusted path. Supplied CI context is
not authenticated CI; control of every expectation can forge agreement. The
flow ends at a local verdict, with no activation or rollback implementation.

[Architecture, source evidence and regeneration](docs/architecture/README.md) ·
[Download interactive HTML](docs/architecture/exact-artifact.html)

GitHub shows HTML as source/download. Use **Download raw file**, then open the
saved standalone HTML locally in a desktop browser.

<a id="try-it"></a>

## Run the example

Requires Python 3.11+ and Git. No dependencies, containers, accounts or credentials.

```sh
git clone https://github.com/wolffrichardj/exact-artifact-demo.git
cd exact-artifact-demo
python3 -m unittest discover -s tests -v
python3 demo.py
```

The demo requires a clean committed checkout. It creates temporary files outside it and removes them when finished. Its output includes a verified artifact and the expected payload-tampering rejection; the overall demonstration exits successfully when that rejection occurs. CI runs these checks without deployment.

To keep an artifact for inspection, choose an empty directory outside the checkout:

```sh
python3 release.py package . /tmp/exact-artifact-output \
  --repository example/sample --workflow synthetic-local --run-id 1 --attempt 1
python3 release.py validate --help
```

Packaging prints paths and identity/digest values. `validate` requires explicit `--repository`, `--workflow`, `--revision`, `--tree`, `--run-id`, `--attempt`, `--expected-sha` and `--expected-manifest` arguments in addition to archive/evidence paths.

A real caller must obtain those expectations through its trusted pipeline. Copying them from an untrusted package establishes only self-consistency. The demo uses local synthetic expectations and makes no external CI provenance claim.

<a id="80-second-walkthrough"></a>

## Watch the 80-second walkthrough

https://github.com/user-attachments/assets/6a80bb12-3ba3-4531-b41f-59c6e717f943

[**Watch or download the captioned walkthrough (MP4)**](docs/walkthrough/walkthrough.mp4)

Immutable-source packaging and payload rejection after the enclosing archive hash is re-pinned.

[Transcript](docs/walkthrough/transcript.txt) · [Captions](docs/walkthrough/captions.srt) · [Reproduce the recorded behavior](docs/walkthrough/reproduce.sh) · [Context and source revision](docs/walkthrough/README.md)

This reviewed video presents genuine recorded output from synthetic fixtures, with neutral synthetic narration. It remains pinned to the earlier source revision recorded alongside the video; README changes do not update that historical recording.

<a id="what-is-checked"></a>

## Follow the checks

| Boundary | Required behavior |
| --- | --- |
| Source | Clean Git root; full commit/tree captured; payload bytes, mode and inventory read from that immutable commit |
| Package | Exactly `public/index.html`, `RELEASE.json`, `MANIFEST.sha256`; stable archive metadata |
| Context | Supplied repository, workflow, commit/tree, run/attempt, push to main and successful conclusion match expected records; this comparison does not authenticate those records |
| Bytes | Independently expected archive and manifest SHA-256; exact manifest membership and each payload digest |
| Structure | Canonical paths and regular files only; reject duplicates, links, extension records, hidden trailing members and missing entries |
| Local bounds | At most 1 MiB compressed and expanded; inspect in memory without extraction |

Start with [`demo.py`](demo.py) for the complete good-package/tamper sequence. In [`release.py`](release.py), `package` reads the immutable Git source, `read_members` enforces the archive boundary, and `validate` binds context, metadata, manifest and payload checks. [`tests/`](tests/) contains adversarial cases.

Validation failures return nonzero with a stable diagnostic category. Tests re-pin enclosing hashes to reach inner checks. The payload-tampering test also temporarily disables the per-file comparison and confirms the corrupted fixture would then be admitted: it checks that the test can detect a missing protection.

<a id="where-it-came-from"></a>

## Scope and lineage

Adapted from Richard Wolff's private website release tooling developed in September and October 2026. The original split CI artifact identity checks from host-side payload verification. This sample retains helpers and adapts those complementary checks into one offline module. [NOTICE.md](NOTICE.md) distinguishes retained code, adapted checks, new hardening and exclusions.

New work here includes immutable Git-object packaging, the fixed synthetic payload, deterministic archive metadata, stricter paths and context records, the independently expected manifest digest, bounded inflation and adversarial tests. These are not claims that every protection already existed in the private source.

This repository starts with the current adaptation. Original historical commits mixed delivery code with private application and operational material; path filtering alone would retain those details in old versions. Original history and exact source mappings remain private. New work is not backdated. Adaptation and review used AI assistance; commit identity does not establish per-line human authorship.

There is no host activation, rollback rehearsal, SSH, SMTP, application runtime or production deployment claim. This is a small local engineering example, not a general-purpose archive service or CI attestation system. No adoption, performance gain or business outcome is claimed. It is personal work, not employer policy or endorsement.

[MIT license](LICENSE) applies to this generalized sample.
