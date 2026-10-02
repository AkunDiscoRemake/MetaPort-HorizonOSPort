// SPDX-License-Identifier: GPL-3.0-only
// Host metadata regression only. These synthetic classes are never installed.
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.HiddenApiRestriction;
import org.jf.dexlib2.Opcodes;
import org.jf.dexlib2.iface.ClassDef;
import org.jf.dexlib2.iface.Method;
import org.jf.dexlib2.immutable.ImmutableClassDef;
import org.jf.dexlib2.immutable.ImmutableDexFile;
import org.jf.dexlib2.immutable.ImmutableMethod;

public final class VerifyDexWriter {
    private static Set<HiddenApiRestriction> expected(String name) {
        return name.equals("LA;")
            ? EnumSet.of(HiddenApiRestriction.WHITELIST, HiddenApiRestriction.TEST_API)
            : EnumSet.of(HiddenApiRestriction.BLACKLIST);
    }
    private static ClassDef definition(String name, String parent) {
        Method method = new ImmutableMethod(name, "m", List.of(), "V", 0x101,
            Set.of(), expected(name), null);
        return new ImmutableClassDef(name, 1, parent, List.of(), null, Set.of(),
            List.of(), List.of(method));
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("match or mismatch");
        boolean expectMismatch = args[0].equals("mismatch");
        if (!expectMismatch && !args[0].equals("match")) throw new IllegalArgumentException("Unknown mode");
        Path path = Files.createTempFile("dex-writer-regression-", ".dex");
        try {
            DexFileFactory.writeDexFile(path.toString(), new ImmutableDexFile(Opcodes.forApi(34),
                List.of(definition("LA;", "LZ;"), definition("LZ;", "Ljava/lang/Object;"))));
            boolean mismatch = false;
            int methods = 0;
            for (ClassDef cls : DexFileFactory.loadDexFile(path.toFile(), Opcodes.forApi(34)).getClasses()) {
                for (Method method : cls.getMethods()) {
                    methods++;
                    mismatch |= !method.getHiddenApiRestrictions().equals(expected(cls.getType()));
                }
            }
            if (methods != 2 || mismatch != expectMismatch)
                throw new IllegalStateException("Unexpected hidden API class association: " + mismatch);
            System.out.println(expectMismatch ? "ORIGINAL_WRITER_MISMATCH_REPRODUCED" : "PATCHED_WRITER_FLAGS_PRESERVED");
        } finally { Files.deleteIfExists(path); }
    }
}
