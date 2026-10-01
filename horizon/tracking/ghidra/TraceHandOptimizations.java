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
        // These names had no direct code references in run 36787226058.
        // Follow a bounded RTTI-layout hypothesis to pointer slots, NOT live calls.
        List<Map<String,Object>> rttiCandidates=new ArrayList<>();
        Set<Long> callbackTargets=new LinkedHashSet<>();
        Set<Long> predictorTargets=new LinkedHashSet<>();
        List<Map<String,Object>> elfPointerFunctions=new ArrayList<>();
        Path pointerFile=out.resolve("hand-optimization-elf-pointers.json");
        if(Files.exists(pointerFile)) {
            var pointerReport=JsonParser.parseString(Files.readString(pointerFile)).getAsJsonObject();
            if(!SHA.equals(pointerReport.get("engine_sha256").getAsString())) throw new IllegalStateException("Pointer evidence hash mismatch");
            for(var targetElement:pointerReport.getAsJsonArray("targets")) {
                var target=targetElement.getAsJsonObject();Set<Long> perType=new LinkedHashSet<>();
                for(var pathElement:target.getAsJsonArray("paths")) {
                    for(var candidate:pathElement.getAsJsonObject().getAsJsonArray("executable_pointer_candidates")) {
                        monitor.checkCancelled();
                        long elf=candidate.getAsJsonObject().get("target_elf").getAsLong();
                        Address address=base.add(elf);var block=currentProgram.getMemory().getBlock(address);
                        if(block==null || !block.isExecute() || (elf&3)!=0) continue;
                        Function f=getFunctionAt(address);
                        if(f==null && getFunctionContaining(address)==null) {
                            disassemble(address);f=createFunction(address,null);
                        }
                        Map<String,Object> row=new LinkedHashMap<>();
                        row.put("type_name",target.get("text").getAsString());row.put("elf_address",elf);
                        row.put("status",f==null?"NO_FUNCTION_AT_CANDIDATE":"FUNCTION_AT_POINTER_CANDIDATE");
                        if(f!=null) row.put("function",describe(f));
                        boolean chosen=f!=null && !f.isExternal() && !f.getName().startsWith("__cxa_") && perType.size()<8 && !perType.contains(elf);
                        if(chosen) {
                            perType.add(elf);
                            (target.get("text").getAsString().contains("DPEPredictorV2")?predictorTargets:callbackTargets).add(elf);
                        }
                        long slot=candidate.getAsJsonObject().get("slot_elf").getAsLong();
                        row.put("pointer_slot_elf",slot);
                        row.put("adjacent_slot_index",(slot-pathElement.getAsJsonObject().get("type_reference_slot_elf").getAsLong()-8)/8);
                        row.put("selected",chosen);row.put("private_abi_validated",false);elfPointerFunctions.add(row);
                    }
                }
            }
        }

        for(var element:targets) {
            var target=element.getAsJsonObject();String text=target.get("text").getAsString();
            if(!text.contains("getHandTrackingThreadPriorityCallback") && !text.contains("DPEPredictorV2")) continue;
            Reference[] nameRefs=getReferencesTo(base.add(target.get("address").getAsLong()));
            for(int n=0;n<Math.min(nameRefs.length,32);n++) {
                monitor.checkCancelled();Address nameSlot=nameRefs[n].getFromAddress();
                var block=currentProgram.getMemory().getBlock(nameSlot);
                if(block==null || block.isExecute() || nameSlot.getOffset()<base.getOffset()+8) continue;
                Address hypotheticalTypeInfo=nameSlot.subtract(8);
                Reference[] typeRefs=getReferencesTo(hypotheticalTypeInfo);
                for(int t=0;t<Math.min(typeRefs.length,32);t++) {
                    Address typeSlot=typeRefs[t].getFromAddress();
                    var typeBlock=currentProgram.getMemory().getBlock(typeSlot);
                    if(typeBlock==null || typeBlock.isExecute()) continue;
                    for(int i=0;i<8;i++) {
                        Address slot=typeSlot.add(8L+i*8L);
                        if(!currentProgram.getMemory().contains(slot)) continue;
                        for(Reference ref:getReferencesFrom(slot)) {
                            Function f=getFunctionAt(ref.getToAddress());
                            if(f==null || f.isExternal() || f.getName().startsWith("__cxa_")) continue;
                            Map<String,Object> row=new LinkedHashMap<>();
                            row.put("type_name",text);row.put("type_name_slot_elf",nameSlot.subtract(base));
                            row.put("hypothetical_typeinfo_elf",hypotheticalTypeInfo.subtract(base));
                            row.put("typeinfo_reference_slot_elf",typeSlot.subtract(base));
                            row.put("pointer_slot_elf",slot.subtract(base));row.put("function",describe(f));
                            row.put("name_references_truncated",nameRefs.length>32);
                            row.put("type_references_truncated",typeRefs.length>32);
                            row.put("private_abi_validated",false);rttiCandidates.add(row);
                            Set<Long> destination=text.contains("DPEPredictorV2")?predictorTargets:callbackTargets;
                            if(destination.size()<8) destination.add(f.getEntryPoint().subtract(base));
                        }
                    }
                }
            }
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
            if(group.getKey().equals("temporal")) selected.addAll(callbackTargets);
            if(group.getKey().equals("inference")) selected.addAll(predictorTargets);
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
                for(long helper:new long[]{0x161c420L,0x161c680L,0x161c820L,0x1616f20L,0x1624fc0L,0x1624a30L,0x1627140L,0xb90838L}) selected.add(helper);
            selections.put(group.getKey(),new ArrayList<>(selected));
            StringBuilder text=new StringBuilder();
            for(long address:selected) text.append(Long.toHexString(address)).append('\n');
            Files.writeString(out.resolve(group.getKey()+"-functions.txt"),text.toString());
        }
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("program_sha256",SHA);report.put("firmware_executed",false);
        report.put("all_optimizations_found",false);report.put("string_reference_coverage",coverage);
        // Fixed-length string copied by recovered 01724fc0 into an output lookup.
        // Preserve bytes instead of guessing that this is temporal state.
        byte[] key=new byte[16];
        if(currentProgram.getMemory().getBytes(base.add(0x39915L),key)!=key.length)
            throw new IllegalStateException("Incomplete DPE output lookup literal");
        boolean printable=true;
        for(byte b:key) if((b&255)<32 || (b&255)>126) printable=false;
        Map<String,Object> literal=new LinkedHashMap<>();
        literal.put("elf_address",0x39915L);literal.put("bytes_hex",HexFormat.of().formatHex(key));
        literal.put("ascii",printable?new String(key,java.nio.charset.StandardCharsets.US_ASCII):null);
        report.put("dpe_output_lookup_literal",literal);
        report.put("elf_pointer_functions",elfPointerFunctions);
        report.put("rtti_pointer_candidates",rttiCandidates);
        report.put("rtti_scope","Hypothesized +8 name field, at most 32 references per level and 8 adjacent pointer slots; not established vtable extent. Up to 8 unique targets per type selected. DPE candidates belong to inference, not scheduling.");
        report.put("incoming_root_calls",edges);report.put("selected_elf_addresses",selections);
        report.put("limits","Direct references only; indirect dispatch and missing function boundaries remain unresolved. Caller selection capped at 16/group; references 128/string, 256/root.");
        Files.writeString(out.resolve("hand-optimization-coverage.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
