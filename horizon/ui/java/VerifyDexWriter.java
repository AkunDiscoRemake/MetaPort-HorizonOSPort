// SPDX-License-Identifier: GPL-3.0-only
// Host metadata regression only. These synthetic classes are never installed.
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.HiddenApiRestriction;
import org.jf.dexlib2.Opcodes;
import org.jf.dexlib2.iface.ClassDef;
import org.jf.dexlib2.iface.Method;
import org.jf.dexlib2.iface.Field;
import org.jf.dexlib2.immutable.ImmutableClassDef;
import org.jf.dexlib2.immutable.ImmutableDexFile;
import org.jf.dexlib2.immutable.ImmutableMethod;
import org.jf.dexlib2.immutable.ImmutableField;

public final class VerifyDexWriter {
    private static Set<HiddenApiRestriction> expected(String name) {
        return name.equals("LA;")
            ? EnumSet.of(HiddenApiRestriction.WHITELIST, HiddenApiRestriction.TEST_API)
            : EnumSet.of(HiddenApiRestriction.BLACKLIST);
    }
    private static ClassDef definition(String name, String parent, int fieldCount) {
        Method method = new ImmutableMethod(name, "m", List.of(), "V", 0x101,
            Set.of(), expected(name), null);
        List<Field> fields = new ArrayList<>();
        if (name.equals("LA;")) {
            for (int i = 0; i < fieldCount; i++)
                fields.add(new ImmutableField(name, "f" + i, "I", 0x81, null, Set.of(), expected(name)));
        }
        return new ImmutableClassDef(name, 1, parent, List.of(), null, Set.of(),
            fields, List.of(method));
    }
    private static int hiddenApiOffset(Path path) throws Exception {
        ByteBuffer bytes = ByteBuffer.wrap(Files.readAllBytes(path)).order(ByteOrder.LITTLE_ENDIAN);
        int map = bytes.getInt(52);
        int count = bytes.getInt(map);
        if (count < 1 || count > 128) throw new IllegalStateException("Map budget");
        for (int i = 0; i < count; i++) {
            int at = map + 4 + i * 12;
            if ((bytes.getShort(at) & 0xffff) == 0xf000) return bytes.getInt(at + 8);
        }
        throw new IllegalStateException("Missing metadata section");
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("match or mismatch");
        boolean expectMismatch = args[0].equals("mismatch");
        if (!expectMismatch && !args[0].equals("match")) throw new IllegalArgumentException("Unknown mode");
        Path path = Files.createTempFile("dex-writer-regression-", ".dex");
        try {
          int misaligned = 0;
          for (int fieldCount = 1; fieldCount <= 4; fieldCount++) {
            DexFileFactory.writeDexFile(path.toString(), new ImmutableDexFile(Opcodes.forApi(34),
                List.of(definition("LA;", "LZ;", fieldCount), definition("LZ;", "Ljava/lang/Object;", fieldCount))));
            if (hiddenApiOffset(path) % 4 != 0) {
                misaligned++;
                if (!expectMismatch) throw new IllegalStateException("Unaligned hidden API section");
            }
            boolean mismatch = false;
            int methods = 0, fields = 0;
            for (ClassDef cls : DexFileFactory.loadDexFile(path.toFile(), Opcodes.forApi(34)).getClasses()) {
                for (Field field : cls.getFields()) {
                    fields++;
                    mismatch |= !field.getHiddenApiRestrictions().equals(expected(cls.getType()));
                }
                for (Method method : cls.getMethods()) {
                    methods++;
                    mismatch |= !method.getHiddenApiRestrictions().equals(expected(cls.getType()));
                }
            }
            if (methods != 2 || fields != fieldCount || mismatch != expectMismatch)
                throw new IllegalStateException("Unexpected hidden API class association: " + mismatch);
          }
            if (expectMismatch && misaligned == 0) throw new IllegalStateException("Alignment fixture did not reproduce original issue");
            System.out.println(expectMismatch ? "ORIGINAL_WRITER_MISMATCH_REPRODUCED" : "PATCHED_WRITER_FLAGS_PRESERVED");
        } finally { Files.deleteIfExists(path); }
    }
}
