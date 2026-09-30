// SPDX-License-Identifier: GPL-3.0-only
// @category MetaPort
// Static reference coverage, NOT execution, activation or ABI validation.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParser;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public class TraceHandOptimizations extends GhidraScript {
    private static final String SHA="10eac37188c97389dabfe7599a354d146d1e6223d849546d230796af93418ffe";
    private Address base;
    private Map<String,Object> describe(Function f) {
        Map<String,Object> row=new LinkedHashMap<>();
        row.put("name",f.getName());row.put("elf_address",f.getEntryPoint().subtract(base));
        return row;
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException("all-strings.json output-directory");
        if(!SHA.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("Wrong original engine");
        base=currentProgram.getImageBase();Path out=Path.of(args[1]);
        var targets=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        if(targets.size()>24576) throw new IllegalArgumentException("Target limit");
        List<Map<String,Object>> coverage=new ArrayList<>();
        for(var element:targets) {
            monitor.checkCancelled();var target=element.getAsJsonObject();
            Reference[] refs=getReferencesTo(base.add(target.get("address").getAsLong()));
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("elf_address",target.get("address").getAsLong());
            row.put("text",target.get("text").getAsString());
            row.put("hand_context_in_string",target.get("hand_context_in_string").getAsBoolean());
            row.put("reference_count",refs.length);
            List<Map<String,Object>> sites=new ArrayList<>();
            for(int i=0;i<Math.min(refs.length,128);i++) {
                Reference ref=refs[i];Map<String,Object> site=new LinkedHashMap<>();
                site.put("elf_address",ref.getFromAddress().subtract(base));
                site.put("reference_type",ref.getReferenceType().toString());
                Function f=getFunctionContaining(ref.getFromAddress());
                if(f!=null && !f.isExternal()) site.put("containing_function",describe(f));
                sites.add(site);
            }
            row.put("sites",sites);row.put("sites_truncated",refs.length>128);coverage.add(row);
        }
        // Roots observed in run 36784585864. ELF VAs; no guessed object layout.
        Map<String,long[]> roots=new LinkedHashMap<>();
        roots.put("inference",new long[]{0x1853880L,0x1618660L});
        roots.put("memory",new long[]{0xd1ec40L,0x1b9b9b0L});
        roots.put("temporal",new long[]{0x183ffd0L,0xa2e090L,0xa69590L});
        List<Map<String,Object>> edges=new ArrayList<>();
        Map<String,Object> selections=new LinkedHashMap<>();
        for(var group:roots.entrySet()) {
            Set<Long> selected=new LinkedHashSet<>();
            for(long root:group.getValue()) {
                Reference[] refs=getReferencesTo(base.add(root));
                Map<String,Object> item=new LinkedHashMap<>();
                item.put("group",group.getKey());item.put("target_elf_address",root);
                item.put("reference_count",refs.length);
                List<Map<String,Object>> calls=new ArrayList<>();
                for(int i=0;i<Math.min(refs.length,256);i++) {
                    monitor.checkCancelled();Reference ref=refs[i];
                    if(!ref.getReferenceType().isCall()) continue;
                    Function f=getFunctionContaining(ref.getFromAddress());
                    Map<String,Object> call=new LinkedHashMap<>();
                    call.put("callsite_elf_address",ref.getFromAddress().subtract(base));
                    if(f!=null && !f.isExternal()) {
                        call.put("caller",describe(f));
                        if(selected.size()<16) selected.add(f.getEntryPoint().subtract(base));
                    }
                    calls.add(call);
                }
                item.put("direct_calls",calls);item.put("scan_truncated",refs.length>256);edges.add(item);
            }
            if(group.getKey().equals("inference"))
                for(long helper:new long[]{0x161c420L,0x161c680L,0x161c820L}) selected.add(helper);
            selections.put(group.getKey(),new ArrayList<>(selected));
            StringBuilder text=new StringBuilder();
            for(long address:selected) text.append(Long.toHexString(address)).append('\n');
            Files.writeString(out.resolve(group.getKey()+"-functions.txt"),text.toString());
        }
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("program_sha256",SHA);report.put("firmware_executed",false);
        report.put("all_optimizations_found",false);report.put("string_reference_coverage",coverage);
        report.put("incoming_root_calls",edges);report.put("selected_elf_addresses",selections);
        report.put("limits","Direct references only; indirect dispatch and missing function boundaries remain unresolved. Caller selection capped at 16/group; references 128/string, 256/root.");
        Files.writeString(out.resolve("hand-optimization-coverage.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
