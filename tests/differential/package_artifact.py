"""Bind the runtime JAR and differential receipt to the clean source commit."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
if dirty.strip():
    raise SystemExit("Refusing to package an artifact from an uncommitted checkout")
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
version = next(line.split("=", 1)[1] for line in (ROOT / "gradle.properties").read_text().splitlines()
               if line.startswith("currentTag="))
jar = ROOT / f"neoforge/build/libs/biolith-neoforge-{version}.jar"
receipt = ROOT / "build/differential/receipt.json"
initializer_receipt = ROOT / "build/mixin-initializers/initializer-receipt.json"
test = json.loads(receipt.read_text())
for relative, expected in test["sources"].items():
    if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
        raise SystemExit(f"Differential receipt is stale: {relative}")
initializer = json.loads(initializer_receipt.read_text())
expected_fields = ["previousUltimateNode", "previousPenultimateNode", "biolith$traversalStack"]
expected_initializer_sources = {
    "tests/mixin_initializers/VerifyInitializers.java", "tests/mixin_initializers/run.py",
    "tests/mixin_initializers/dependencies.json",
    "common/src/main/java/com/terraformersmc/biolith/impl/mixin/MixinSearchTree.java",
}
lock = json.loads((ROOT / "tests/mixin_initializers/dependencies.json").read_bytes())
expected_dependencies = {f"{row['name']}-{row['version']}.jar": row["sha256"] for row in lock}
if (initializer.get("verified") is not True or initializer.get("extracted_fields") != expected_fields
        or initializer.get("artifact") != jar.name
        or initializer.get("artifact_sha256") != hashlib.sha256(jar.read_bytes()).hexdigest()
        or initializer.get("dependencies") != expected_dependencies
        or set(initializer.get("sources", {})) != expected_initializer_sources):
    raise SystemExit("Real-Mixin initializer receipt does not verify this runtime artifact")
for relative, expected in initializer["sources"].items():
    if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
        raise SystemExit(f"Real-Mixin initializer receipt is stale: {relative}")
out = ROOT / "build/candidate"
out.mkdir(parents=True, exist_ok=True)
for source in (jar, receipt, initializer_receipt, ROOT / "LICENSE", ROOT / "docs/BIOLITH_CPS_CANDIDATE.md"):
    shutil.copy2(source, out / source.name)
provenance = {
    "repository": "zublastic-dot/Biolith",
    "source_commit": commit,
    "upstream_commit": test["upstream_commit"],
    "version": version,
    "artifact": jar.name,
    "artifact_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
    "github_run_id": os.environ.get("GITHUB_RUN_ID"),
    "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    "differential_result": test["result"],
    "mixin_initializer_verified": True,
    "mixin_initializer_receipt_sha256": hashlib.sha256(initializer_receipt.read_bytes()).hexdigest(),
    "mixin_initializer_dependencies": expected_dependencies,
    "limitations": "Algorithm parity uses exact Java with Minecraft type doubles; the separate real-Mixin gate verifies built field initialization. Full live runtime and CPS acceptance remain separate."
}
(out / "BUILD_PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n")
print(json.dumps(provenance, indent=2))
