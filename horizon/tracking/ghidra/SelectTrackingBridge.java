// SPDX-License-Identifier: GPL-3.0-only
// @category MetaPort
// Inspect small original dependency shims, not replacements or ABI validation.
import ghidra.app.script.GhidraScript;
import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public class SelectTrackingBridge extends GhidraScript {
    private static final Set<String> SHAS=Set.of(
        "7a1a81acb7b42c143866c8536768465569109cb316fd26e21115972a1ab2fd28",
        "a83d12685803d32eae269c7d8b9b168c614fc9dcccefd03b9aa8e3250803afa5");
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=1) throw new IllegalArgumentException("report-prefix");
        String sha=currentProgram.getExecutableSHA256().toLowerCase(Locale.ROOT);
        if(!SHAS.contains(sha)) throw new IllegalStateException("Wrong original tracking bridge");
        var base=currentProgram.getImageBase();
        var iterator=currentProgram.getFunctionManager().getFunctions(true);
        List<Map<String,Object>> functions=new ArrayList<>();StringBuilder addresses=new StringBuilder();
        int candidates=0,selected=0;
        while(iterator.hasNext()) {
            monitor.checkCancelled();var f=iterator.next();
            var block=currentProgram.getMemory().getBlock(f.getEntryPoint());
            if(f.isExternal() || f.isThunk() || block==null || !block.isExecute()) continue;
            candidates++;
            if(selected>=24) continue;
            long elf=f.getEntryPoint().subtract(base);selected++;
            addresses.append(Long.toHexString(elf)).append('\n');
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("name",f.getName());row.put("elf_address",elf);functions.add(row);
        }
        if(selected==0) throw new IllegalStateException("No bridge code functions recovered");
        Files.writeString(Path.of(args[0]+"-functions.txt"),addresses.toString());
        Files.writeString(Path.of(args[0]+"-strings.json"),"[]\n");
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("program_sha256",sha);report.put("candidate_count",candidates);
        report.put("functions",functions);report.put("selection_truncated",candidates>24);
        report.put("firmware_executed",false);report.put("private_abi_validated",false);
        report.put("scope","Up to 24 auto-discovered executable non-thunk functions; missing boundaries and indirect dispatch unresolved. Not all software optimizations.");
        Files.writeString(Path.of(args[0]+"-selection.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
