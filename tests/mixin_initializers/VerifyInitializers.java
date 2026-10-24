import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipFile;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.AbstractInsnNode;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.FieldInsnNode;
import org.spongepowered.asm.mixin.injection.struct.Constructor;
import org.spongepowered.asm.mixin.transformer.struct.InsnRange;

/** Exercise the runtime Mixin extractor on the remapped artifact, not a copy of its algorithm. */
public final class VerifyInitializers {
    private static final List<String> EXPECTED = List.of(
            "previousUltimateNode", "previousPenultimateNode", "biolith$traversalStack");

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 1) throw new IllegalArgumentException("Expected one built runtime JAR");
        try (ZipFile jar = new ZipFile(Path.of(arguments[0]).toFile())) {
            var entry = jar.getEntry("com/terraformersmc/biolith/impl/mixin/MixinSearchTree.class");
            if (entry == null) throw new AssertionError("Runtime artifact lacks the production mixin");
            var node = new ClassNode();
            new ClassReader(jar.getInputStream(entry).readAllBytes()).accept(node, 0);
            var constructors = node.methods.stream().filter(method -> method.name.equals("<init>")).toList();
            if (constructors.size() != 1) throw new AssertionError("Expected one production mixin constructor");
            var constructor = constructors.getFirst();
            // Initialiser.initInstructions invokes this exact pair of runtime methods.
            InsnRange range = Constructor.getRange(constructor);
            if (!range.isValid()) throw new AssertionError("Mixin rejected constructor range: " + range);
            var extracted = new ArrayList<String>();
            for (AbstractInsnNode instruction : range.apply(constructor.instructions, false)) {
                if (instruction instanceof FieldInsnNode field && field.getOpcode() == Opcodes.PUTFIELD) {
                    if (!field.owner.equals(node.name) || !field.desc.equals("Ljava/lang/ThreadLocal;"))
                        throw new AssertionError("Unexpected extracted field assignment: " + field.name);
                    extracted.add(field.name);
                }
            }
            if (!extracted.equals(EXPECTED)) {
                throw new AssertionError("Mixin must inject all three cache initializers exactly once; extracted="
                        + extracted + ", range=" + range);
            }
            System.out.println("{\"verified\":true,\"constructor_range\":\"" + range
                    + "\",\"extracted_fields\":[\"" + String.join("\",\"", extracted) + "\"]}");
        }
    }
}
