// SPDX-License-Identifier: GPL-3.0-only
// Exact, declared app-scope transport adaptation; never replace Android boot classes.
import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.jf.baksmali.Baksmali;
import org.jf.baksmali.BaksmaliOptions;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.Opcodes;
import org.jf.dexlib2.iface.ClassDef;
import org.jf.dexlib2.iface.DexFile;
import org.jf.dexlib2.immutable.ImmutableDexFile;
import org.jf.dexlib2.rewriter.DexRewriter;
import org.jf.dexlib2.rewriter.Rewriter;
import org.jf.dexlib2.rewriter.RewriterModule;
import org.jf.dexlib2.rewriter.Rewriters;
import org.jf.dexlib2.rewriter.TypeRewriter;

public final class AdaptServiceTransport {
    private static final Set<String> OWNERS = Set.of("Loculus/internal/osutils/BinderClient;",
        "Loculus/internal/osutils/BinderClient$ServiceManagerCallback;");
    private static final Map<String, String> TYPES = Map.of(
        "Landroid/os/IServiceCallback;", "Lorg/metaport/port/services/ServiceCallback;",
        "Landroid/os/IServiceCallback$Stub;", "Lorg/metaport/port/services/ServiceCallback$Stub;",
        "Landroid/os/ServiceManager;", "Lorg/metaport/port/services/ServiceDirectory;");
    public static void main(String[] args) throws Exception {
        if (args.length != 4) throw new IllegalArgumentException("input output before after");
        File input = new File(args[0]);
        if (input.length() < 112 || input.length() > 32*1024*1024) throw new IllegalArgumentException("Input budget");
        DexFile source = DexFileFactory.loadDexFile(input, Opcodes.forApi(34));
        DexRewriter rewriter = new DexRewriter(new RewriterModule() {
            @Override public Rewriter<String> getTypeRewriter(Rewriters rewriters) {
                return new TypeRewriter() {
                    @Override protected String rewriteUnwrappedType(String type) {
                        return TYPES.getOrDefault(type, type);
                    }
                };
            }
        });
        List<ClassDef> classes = new ArrayList<>();
        int changed = 0;
        for (ClassDef cls : source.getClasses()) {
            if (OWNERS.contains(cls.getType())) {
                classes.add(rewriter.getClassDefRewriter().rewrite(cls)); changed++;
            } else classes.add(cls);
        }
        if (changed != OWNERS.size()) throw new IllegalStateException("Missing transport owners");
        DexFileFactory.writeDexFile(args[1], new ImmutableDexFile(source.getOpcodes(), classes));
        DexFile output = DexFileFactory.loadDexFile(args[1], source.getOpcodes());
        BaksmaliOptions options = new BaksmaliOptions(); options.apiLevel = 34;
        if (!Baksmali.disassembleDexFile(source, new File(args[2]), 2, options)
                || !Baksmali.disassembleDexFile(output, new File(args[3]), 2, options))
            throw new IllegalStateException("Disassembly failed");
    }
}
