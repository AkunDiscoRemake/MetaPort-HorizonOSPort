// SPDX-License-Identifier: GPL-3.0-only
// Host-only regression: no firmware classes are executed or replaced.
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.Opcodes;
import org.jf.dexlib2.iface.Field;
import org.jf.dexlib2.iface.value.EncodedValue;
import org.jf.dexlib2.immutable.ImmutableClassDef;
import org.jf.dexlib2.immutable.ImmutableDexFile;
import org.jf.dexlib2.immutable.ImmutableField;
import org.jf.dexlib2.immutable.value.ImmutableBooleanEncodedValue;
import org.jf.dexlib2.immutable.value.ImmutableIntEncodedValue;
import org.jf.dexlib2.immutable.value.ImmutableNullEncodedValue;

public final class VerifyStaticInitializers {
    private static Field field(String name, String type, EncodedValue value) {
        return new ImmutableField("LB;", name, type, 9, value, Set.of(), Set.of());
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !(args[0].equals("match") || args[0].equals("mismatch")))
            throw new IllegalArgumentException("match or mismatch");
        List<Field> fields = List.of(
            field("a", "I", new ImmutableIntEncodedValue(7)),
            field("b", "Z", ImmutableBooleanEncodedValue.FALSE_VALUE),
            field("c", "I", new ImmutableIntEncodedValue(0)),
            field("d", "Ljava/lang/String;", ImmutableNullEncodedValue.INSTANCE),
            field("e", "Ljava/lang/String;", null));
        Path path = Files.createTempFile("dex-static-regression-", ".dex");
        try {
            ImmutableClassDef cls = new ImmutableClassDef("LB;", 1, "Ljava/lang/Object;",
                List.of(), null, Set.of(), fields, List.of());
            DexFileFactory.writeDexFile(path.toString(), new ImmutableDexFile(Opcodes.forApi(34), List.of(cls)));
            int count = 0, changed = 0;
            for (Field actual : DexFileFactory.loadDexFile(path.toFile(), Opcodes.forApi(34))
                    .getClasses().iterator().next().getStaticFields()) {
                Field expected = fields.get(count++);
                if (!expected.getName().equals(actual.getName())) throw new IllegalStateException("Field order");
                if (!java.util.Objects.equals(expected.getInitialValue(), actual.getInitialValue())) changed++;
            }
            int expectedChanges = args[0].equals("mismatch") ? 3 : 0;
            if (count != 5 || changed != expectedChanges)
                throw new IllegalStateException("Unexpected initializer changes: " + changed);
            System.out.println(expectedChanges == 0 ? "PATCHED_EXPLICIT_INITIALIZERS_PRESERVED" : "ORIGINAL_INITIALIZERS_TRIMMED");
        } finally { Files.deleteIfExists(path); }
    }
}
