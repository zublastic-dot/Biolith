# Biolith traversal bookkeeping candidate

This fork is based on TerraformersMC/Biolith 3.0.14, commit
`996b7a468ce7c36d2883e70eae3a8c87a30bae63`, for Minecraft 1.21.1.
The modified build identifies itself as `3.0.14+zublastic.1`. It retains the
upstream LGPL license, authorship and dependency versions. The remote Ferry
build script is pinned to commit `dc829e34d7a719e518bc1ad3a4757421b26f14c7`;
upstream Architectury/Loom snapshot plugin declarations remain unchanged.

The only gameplay-path change replaces each search's iterator array and
per-branch iterator objects with reusable, per-tree, per-thread arrays of
child-array references and cursors. The original traversal order, distance
callback order, strict comparisons, different-biome rule, fallback caches,
64-frame limit, query-parameter allocation and immutable results are retained.
Reentrant calls receive separate scratch state. A `finally` block clears all
used references and releases scratch state after normal and exceptional exits.
The helper is a public external class so its access remains valid after Mixin
copies the search into Minecraft's target class.

This introduces a small fixed scratch object per participating thread and
search tree, approximately two 64-element arrays plus their holder. It removes
repeated traversal allocations after initialization, except for unusual nested
distance callbacks. It makes no promise about CPS or pause-time improvements.

## Validation

Run with Java 21 and Python 3:

```
python -B tests/differential/run.py
bash ./gradlew :neoforge:remapJar --no-daemon --console=plain
```

The differential harness reads the original Java directly from the pinned Git
commit and compiles it alongside the exact production Java. Minimal Minecraft
type doubles allow deterministic testing of control flow and node identity.
Tests cover ties, duplicate-biome leaves, warm fallback caches, callback order,
random trees, nested callbacks before and during traversal, callback exceptions,
malformed trees, the depth bound, cleanup and concurrent threads. This checks
algorithm parity; it does not execute the Minecraft Mixin transformer.

The `Biolith CPS Candidate` workflow runs that harness and the NeoForge remap
build. Its `biolith-neoforge-candidate` artifact includes the runtime JAR,
SHA-256/source-commit provenance, differential receipt, this document and the
license. Packaging refuses an uncommitted source tree or stale source hashes.

Deploy only the artifact from the successful workflow for the selected commit.
Real-server startup/Mixin acceptance, matching-world output checks, and repeated
controlled CPS measurements are separate acceptance gates. A local successful
build or allocation reduction alone is not a measured server performance gain.
