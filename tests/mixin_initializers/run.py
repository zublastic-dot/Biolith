"""Verify built field initialization using the exact hash-pinned live Mixin extractor.

The runtime library matches the observed Kinetic Mixin 0.16.4+mixin.0.8.7.
Its Constructor.getRange/InsnRange.apply methods perform the real extraction;
no Minecraft test double or reimplementation decides which initializers survive.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "build/mixin-initializers"
LOCK = HERE / "dependencies.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dependency(row):
    name = f"{row['name']}-{row['version']}.jar"
    target = OUT / "dependencies" / name
    if target.exists() and sha(target.read_bytes()) == row["sha256"]:
        return target
    # The build commonly already has the exact artifacts. Reuse only matching
    # bytes; a matching filename or Maven coordinate is not sufficient.
    cache = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
    directory = cache / "caches/modules-2/files-2.1" / row["group"] / row["name"] / row["version"]
    raw = next((path.read_bytes() for path in directory.glob("*/" + name)
                if sha(path.read_bytes()) == row["sha256"]), None)
    if raw is None:
        url = "/".join((row["repository"], row["group"].replace(".", "/"),
                        row["name"], row["version"], name))
        with urlopen(url, timeout=60) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024 or sha(raw) != row["sha256"]:
        raise RuntimeError("Pinned Mixin regression dependency differs: " + name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, help="Defaults to the current NeoForge build; old candidates must fail")
    args = parser.parse_args()
    version = next(line.split("=", 1)[1] for line in (ROOT / "gradle.properties").read_text().splitlines()
                   if line.startswith("currentTag="))
    artifact = args.artifact or ROOT / f"neoforge/build/libs/biolith-neoforge-{version}.jar"
    if not artifact.is_file() or not 0 < artifact.stat().st_size <= 4 * 1024 * 1024:
        raise RuntimeError("Missing or oversized built runtime artifact")
    artifact_sha = sha(artifact.read_bytes())
    dependencies = json.loads(LOCK.read_bytes())
    classpath = os.pathsep.join(str(dependency(row)) for row in dependencies)
    classes = OUT / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    java_home = Path(os.environ.get("JAVA_HOME", "C:/Program Files/Java/jdk-21"))
    java = str(java_home / "bin/java.exe") if (java_home / "bin/java.exe").exists() else shutil.which("java")
    javac = str(java_home / "bin/javac.exe") if (java_home / "bin/javac.exe").exists() else shutil.which("javac")
    subprocess.run([javac, "--release", "21", "-proc:none", "-cp", classpath, "-d", str(classes),
                    str(HERE / "VerifyInitializers.java")], check=True)
    run = subprocess.run([java, "-cp", str(classes) + os.pathsep + classpath, "VerifyInitializers",
                          str(artifact.resolve())], text=True, capture_output=True)
    if run.returncode:
        raise RuntimeError("Real-Mixin artifact initializer regression failed:\n" + run.stdout + run.stderr)
    result = json.loads(run.stdout)
    if sha(artifact.read_bytes()) != artifact_sha:
        raise RuntimeError("Built artifact changed during verification")
    sources = [HERE / "VerifyInitializers.java", HERE / "run.py", LOCK,
               ROOT / "common/src/main/java/com/terraformersmc/biolith/impl/mixin/MixinSearchTree.java"]
    receipt = dict(result, artifact=artifact.name, artifact_sha256=artifact_sha,
        dependencies={path.name: sha(path.read_bytes()) for path in (dependency(row) for row in dependencies)},
        sources={str(path.relative_to(ROOT)).replace("\\", "/"): sha(path.read_bytes()) for path in sources},
        scope="Exact runtime Mixin constructor initializer extraction on the built JAR; full game startup and CPS remain separate.")
    (OUT / "initializer-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
