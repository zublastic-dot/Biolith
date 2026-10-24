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
test = json.loads(receipt.read_text())
for relative, expected in test["sources"].items():
    if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
        raise SystemExit(f"Differential receipt is stale: {relative}")
out = ROOT / "build/candidate"
out.mkdir(parents=True, exist_ok=True)
for source in (jar, receipt, ROOT / "LICENSE", ROOT / "docs/BIOLITH_CPS_CANDIDATE.md"):
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
    "limitations": "Parity uses exact Java against Minecraft type doubles; live runtime and CPS acceptance remain separate."
}
(out / "BUILD_PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n")
print(json.dumps(provenance, indent=2))
