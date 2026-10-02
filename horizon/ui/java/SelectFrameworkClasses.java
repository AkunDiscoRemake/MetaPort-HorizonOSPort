// SPDX-License-Identifier: GPL-3.0-only
// Host-only class selection. No class is loaded or instantiated from firmware.
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.jf.baksmali.Baksmali;
import org.jf.baksmali.BaksmaliOptions;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.Opcodes;
import org.jf.dexlib2.iface.ClassDef;
import org.jf.dexlib2.iface.DexFile;
import org.jf.dexlib2.immutable.ImmutableDexFile;

public final class SelectFrameworkClasses {
    public static void main(String[] args) throws Exception {
        if (args.length != 5) throw new IllegalArgumentException("input output selection before after");
        File input = new File(args[0]);
        if (input.length() < 112 || input.length() > 32 * 1024 * 1024)
            throw new IllegalArgumentException("DEX input budget");
        List<String> names = Files.readAllLines(Path.of(args[2]));
        Set<String> wanted = new HashSet<>(names);
        if (wanted.isEmpty() || names.size() != wanted.size() || names.size() > 4096)
            throw new IllegalArgumentException("Selection budget/duplicates");
        DexFile source = DexFileFactory.loadDexFile(input, Opcodes.forApi(34));
        List<ClassDef> selected = new ArrayList<>();
        for (ClassDef definition : source.getClasses())
            if (wanted.contains(definition.getType())) selected.add(definition);
        if (selected.size() != wanted.size()) throw new IllegalArgumentException("Missing selected definition");
        DexFileFactory.writeDexFile(args[1], new ImmutableDexFile(source.getOpcodes(), selected));
        DexFile output = DexFileFactory.loadDexFile(args[1], source.getOpcodes());
        BaksmaliOptions options = new BaksmaliOptions();
        options.apiLevel = 34;
        if (!Baksmali.disassembleDexFile(source, new File(args[3]), 2, options, names)
                || !Baksmali.disassembleDexFile(output, new File(args[4]), 2, options, names))
            throw new IllegalStateException("Canonical disassembly failed");
        System.out.println("Selected original definitions: " + selected.size());
    }
}
