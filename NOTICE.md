# Derivation and scope

Copyright (c) 2026 Richard Wolff. Released under the accompanying MIT license.

This generalized sample adapts the author's private website release tooling, developed in September and October 2026. The original business repository remains private. A private ledger retains exact source revisions, file hashes and function mappings.

Retained code: `require`, `read_field` and `path_name` are copied from the original Python release validators. Adapted code: archive/member safety checks, metadata binding, manifest parsing and exact file/hash comparison; allowlisted packaging and commit/tree/clean metadata follow the original packaging script. The original CI identity validator and host payload validator were complementary checks, not one standalone verifier.

New work in this sample includes immutable Git-object packaging, one fixed synthetic payload, deterministic tar/gzip metadata, stricter canonical paths and evidence records, explicit workflow-name/conclusion expectations, an independently expected manifest digest, exact metadata types, bounded inflation without extraction, stable failure categories, a local demo and isolated adversarial tests. These additions do not establish that the private source already had all these guarantees.

Original CI/deployment tests informed the rejection scenarios. The tests here are newly authored for the synthetic sample and cover both identity and payload layers. No original application, business content, operational configuration, host identifiers, dependency trees, private records or assets are included. Python's standard library is used; no third-party code is vendored. The verification workflow references GitHub's checkout action at an explicit commit.

No historical Git commits are imported or re-created. This adaptation is newly committed at its actual date. Original authorship and dates remain in private source history; their absence from the public contribution graph is intentional, not a rewritten development timeline.
