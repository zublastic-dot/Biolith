# Biolith traversal bookkeeping candidate

This fork is based on TerraformersMC/Biolith 3.0.14, commit
`996b7a468ce7c36d2883e70eae3a8c87a30bae63`, for Minecraft 1.21.1.
The modified build identifies itself as `3.0.14+zublastic.2`. It retains the
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
python -B tests/mixin_initializers/run.py
```

The differential harness reads the original Java directly from the pinned Git
commit and compiles it alongside the exact production Java. Minimal Minecraft
type doubles allow deterministic testing of control flow and node identity.
Tests cover ties, duplicate-biome leaves, warm fallback caches, callback order,
random trees, nested callbacks before and during traversal, callback exceptions,
malformed trees, the depth bound, cleanup and concurrent threads. This checks
algorithm parity; it does not execute the Minecraft Mixin transformer.

The `.1` candidate failed before measured generation: Mixin omitted both old
fallback-cache field initializers. Javac placed the constructor's final line
number at the annotation preceding the multiline method-reference initializer.
Mixin interpreted that expanded line range as constructor body and extracted
only the new traversal stack initializer. This was reproduced using the exact
installed Mixin `0.16.4+mixin.0.8.7` bytes and both built artifacts; no third-party
cache redirect was found. The `.2` repair keeps the annotation and complete
initializer on one physical line, without changing traversal logic or caches.

The separate artifact gate calls that real Mixin library's `Constructor.getRange`
and `InsnRange.apply`, exactly as its initializer extractor does. It requires all
three field assignments once in the remapped runtime JAR. Dependencies are
SHA-256 pinned in `tests/mixin_initializers/dependencies.json`; the Mixin hash was
matched against the running Kinetic library. The same gate rejects the failed
`.1` artifact. This tests initializer extraction, not a full Minecraft startup.

The `Biolith CPS Candidate` workflow runs both gates and the NeoForge remap
build. Its artifact includes the runtime JAR, SHA-256/source-commit provenance,
differential and initializer receipts, this document and the license. Packaging
refuses an uncommitted tree, stale source hashes, wrong artifact hash, missing
initializers or changed regression dependencies.

Deploy only the artifact from the successful workflow for the selected commit.
Real-server startup/Mixin acceptance, matching-world output checks, and repeated
controlled CPS measurements are separate acceptance gates. A local successful
build or allocation reduction alone is not a measured server performance gain.
