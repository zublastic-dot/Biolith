"""Compile the exact production search against the pinned upstream search.

The generated Minecraft types are deliberately minimal test doubles. This checks
control-flow, identity and callback parity, not Minecraft runtime integration.
The NeoForge remap/build and real-server acceptance are separate requirements.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PIN = "996b7a468ce7c36d2883e70eae3a8c87a30bae63"
REL = "common/src/main/java/com/terraformersmc/biolith/impl/mixin/MixinSearchTree.java"
OUT = ROOT / "build/differential"
SRC = OUT / "src"
CLASSES = OUT / "classes"
SRC.mkdir(parents=True, exist_ok=True)
CLASSES.mkdir(parents=True, exist_ok=True)


def write(name, source):
    path = SRC / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf8")


reference = subprocess.check_output(["git", "show", f"{PIN}:{REL}"], cwd=ROOT)
write("com/terraformersmc/biolith/impl/mixin/ReferenceSearchTree.java",
      reference.decode().replace("class MixinSearchTree<T>", "class ReferenceSearchTree<T>"))
production_paths = [REL,
    "common/src/main/java/com/terraformersmc/biolith/impl/biome/SearchTreeTraversalStack.java",
    "common/src/main/java/com/terraformersmc/biolith/impl/biome/SimpleArrayIterator.java",
    "common/src/main/java/com/terraformersmc/biolith/impl/biome/InterfaceSearchTree.java",
    "common/src/main/java/com/terraformersmc/biolith/api/biome/BiolithFittestNodes.java"]
for path in production_paths:
    write(path.split("/src/main/java/", 1)[1], (ROOT / path).read_text())

for package, names in [("org.spongepowered.asm.mixin", ["Final", "Mixin", "Shadow", "Unique"]),
                       ("org.jetbrains.annotations", ["NotNull", "Nullable"])]:
    for name in names:
        write(package.replace(".", "/") + "/" + name + ".java",
              f"package {package}; public @interface {name} {{ Class<?>[] value() default {{}}; }}")
write("net/minecraft/util/Identifier.java", """
package net.minecraft.util;
public record Identifier(String namespace, String path) {
    public static Identifier of(String namespace, String path) { return new Identifier(namespace, path); }
}
""")
write("net/minecraft/registry/RegistryKey.java", """
package net.minecraft.registry;
import net.minecraft.util.Identifier;
public record RegistryKey<T>(Identifier value) {
    public Identifier getValue() { return value; }
    public static <T> RegistryKey<T> of(RegistryKey<?> registry, Identifier value) { return new RegistryKey<>(value); }
}
""")
write("net/minecraft/registry/RegistryKeys.java", """
package net.minecraft.registry;
import net.minecraft.util.Identifier;
public class RegistryKeys { public static final RegistryKey<Object> BIOME = new RegistryKey<>(Identifier.of("test", "biome")); }
""")
write("net/minecraft/registry/entry/RegistryEntry.java", """
package net.minecraft.registry.entry;
import net.minecraft.registry.RegistryKey;
import java.util.Optional;
public record RegistryEntry<T>(RegistryKey<T> key) {
    public Optional<RegistryKey<T>> getKey() { return Optional.of(key); }
}
""")
write("com/terraformersmc/biolith/impl/Biolith.java", """
package com.terraformersmc.biolith.impl;
public class Biolith {
    public static final String MOD_ID = "biolith";
    public static final Logger LOGGER = new Logger();
    public static class Logger { public void error(String message) {} }
}
""")
write("net/minecraft/world/biome/source/util/MultiNoiseUtil.java", """
package net.minecraft.world.biome.source.util;
public class MultiNoiseUtil {
    public record NoiseValuePoint(long[] parameters) {
        public long[] getNoiseValueList() { return parameters.clone(); }
    }
    public interface NodeDistanceFunction<T> {
        long getDistance(SearchTree.TreeNode<T> node, long[] point);
    }
    public static class SearchTree<T> {
        public static class TreeNode<T> {
            public final int id;
            public final long[] min, max;
            public TreeNode(int id, long[] min, long[] max) { this.id=id; this.min=min; this.max=max; }
        }
        public static class TreeLeafNode<T> extends TreeNode<T> {
            public final T value;
            public TreeLeafNode(int id, T value, long[] point) { super(id,point,point); this.value=value; }
        }
        public static class TreeBranchNode<T> extends TreeNode<T> {
            public TreeNode<T>[] subTree;
            public TreeBranchNode(int id, TreeNode<T>[] children, long[] min, long[] max) {
                super(id,min,max); subTree=children;
            }
        }
    }
}
""")
write("Differential.java", (ROOT / "tests/differential/Differential.java").read_text())
java_home = Path(os.environ.get("JAVA_HOME", "C:/Program Files/Java/jdk-21"))
java = str(java_home / "bin/java.exe") if (java_home / "bin/java.exe").exists() else shutil.which("java")
javac = str(java_home / "bin/javac.exe") if (java_home / "bin/javac.exe").exists() else shutil.which("javac")
sources = sorted(str(path) for path in SRC.rglob("*.java"))
subprocess.run([javac, "--release", "21", "-d", str(CLASSES), *sources], check=True)
run = subprocess.run([java, "-ea", "-cp", str(CLASSES), "Differential"], check=True,
                     text=True, capture_output=True)
print(run.stdout, end="")
receipt = {"upstream_commit": PIN, "reference_sha256": hashlib.sha256(reference).hexdigest(),
           "sources": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in production_paths},
           "result": run.stdout.strip(),
           "scope": "Exact production Java vs pinned upstream Java with test doubles; not runtime integration or CPS"}
(OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
