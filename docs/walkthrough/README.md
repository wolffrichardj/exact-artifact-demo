# Exact Artifact Demo walkthrough

An 80-second presentation of genuinely recorded local output, with synthetic fixtures. Neutral synthetic narration uses the installed macOS Samantha voice, not Richard's voice. JSON fields are selected/reflowed; diagrams explain boundaries and excerpts identify public source.

## Reproduce the source behavior

Requires Python 3.11+ and Git. Run `sh reproduce.sh` from this directory. The script clones public source into a fresh temporary workspace, checks out the exact revision, runs the source tests and scenario assertions, then prints/retains its workspace for inspection. It does not change an existing checkout or delete the retained workspace.

Repository: https://github.com/wolffrichardj/exact-artifact-demo

Revision: `076da3474dbbac3f3cd882dd3b37403501933c56`

The exact commands are in `reproduce.sh`; actual recorded results and shot mapping are in `evidence.json`. `source-manifest.json` contains the pinned source-file hashes. Scripts reproduce source behavior, not bit-identical audiovisual rendering. Production used Python/Pillow, local macOS speech synthesis and ffmpeg; cue timing and render checks are retained in the production evidence. No paid service was used.

## Boundaries

This source-derived sample packages one synthetic HTML page, metadata and a manifest from a captured immutable Git commit. Validation binds source, context, exact inventory and payload digests to supplied expectations. The demonstration uses local synthetic expectations. Its test constructor replaces payload bytes and repins the outer digest in evidence and expectation, retaining the original per-file manifest to reach the inner rejection. A real caller must obtain expectations from an independently trusted route. If every expected input is controlled, agreement can be forged. Hash consistency is not a signature or authenticated CI attestation. The sample has 1 MiB compressed/expanded bounds and checks in memory without extraction. It performs no production activation or rollback. The demo exits 0 because valid validation and expected payload rejection both occurred.

## Attribution

Adapted from Richard Wolff's private release tooling, with new hardening and AI-assisted adaptation/review. This public adaptation begins at its actual date; no private history or source maps are included. See the public repository's NOTICE.md and MIT license. No adoption, performance, production deployment or business outcome is claimed.

## Files

`walkthrough.mp4` has burned captions and an optional embedded English subtitle track. `captions.srt`/`captions.vtt` and `transcript.txt` provide reusable text. The local index plays the media without external dependencies.
