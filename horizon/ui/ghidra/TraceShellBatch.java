// SPDX-License-Identifier: GPL-3.0-only
// @category MetaPort
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import com.google.gson.GsonBuilder;
import java.nio.file.*;
import java.util.*;

/** One import, bounded two-level frontier, incremental evidence. Never executes firmware. */
public class TraceShellBatch extends GhidraScript {
    private final Map<String,Object> report=new LinkedHashMap<>();
    private Path output;
    private void save() throws Exception {
        Path temp=output.resolveSibling(output.getFileName()+".tmp");
        Files.writeString(temp,new GsonBuilder().setPrettyPrinting().create().toJson(report));
        Files.move(temp,output,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2 && args.length!=3) throw new IllegalArgumentException("roots-file output-json [function-cap]");
        int cap=args.length==3 ? Integer.parseInt(args[2]) : 96;
        if(cap<1 || cap>96) throw new IllegalArgumentException("Function budget");
        output=Path.of(args[1]);
        Address base=currentProgram.getImageBase();
        List<String> roots=Files.readAllLines(Path.of(args[0]));
        if(roots.isEmpty() || roots.size()>Math.min(64,cap)) throw new IllegalArgumentException("Root budget");
        LinkedHashSet<Address> selected=new LinkedHashSet<>();
        for(String root:roots) selected.add(base.add(Long.parseUnsignedLong(root.trim(),16)));
        report.put("program_sha256",currentProgram.getExecutableSHA256());
        report.put("image_base",base.toString());
        report.put("root_count",selected.size());
        report.put("function_cap",cap);
        report.put("identified_function_count_not_total_original",currentProgram.getFunctionManager().getFunctionCount());
        report.put("scope","At most two Ghidra called-function levels; indirect targets unresolved; analyzer prototypes may be wrong");
        report.put("firmware_executed",false);
        report.put("private_abi_validated",false);
        report.put("all_horizon_disassembled",false);
        List<Map<String,Object>> frontier=new ArrayList<>();
        List<Address> level=new ArrayList<>(selected);
        boolean capped=selected.size()>=cap;
        for(int depth=0;depth<2 && selected.size()<cap;depth++) {
            List<List<Address>> candidates=new ArrayList<>();
            for(Address address:level) {
                monitor.checkCancelled();
                Function f=getFunctionAt(address);
                List<Address> children=new ArrayList<>();
                if(f!=null) for(Function target:f.getCalledFunctions(monitor)) {
                    Address a=target.getEntryPoint();
                    var block=currentProgram.getMemory().getBlock(a);
                    if(!target.isExternal() && !target.isThunk() && block!=null && block.isExecute()) children.add(a);
                }
                children.sort(Address::compareTo);
                Map<String,Object> row=new LinkedHashMap<>();
                row.put("elf_address",address.subtract(base));row.put("depth",depth);
                row.put("eligible_callee_count",children.size());
                List<Long> shown=new ArrayList<>();
                for(Address a:children.subList(0,Math.min(children.size(),128))) shown.add(a.subtract(base));
                row.put("callees",shown);row.put("callees_truncated",children.size()>128);frontier.add(row);
                candidates.add(children.subList(0,Math.min(children.size(),128)));
                capped|=children.size()>128;
            }
            List<Address> next=new ArrayList<>();
            for(int rank=0;rank<128;rank++) for(List<Address> list:candidates) if(rank<list.size()) {
                Address a=list.get(rank);
                if(selected.contains(a)) continue;
                if(selected.size()==cap) { capped=true;continue; }
                selected.add(a);next.add(a);
            }
            level=next;
        }
        report.put("frontier",frontier);report.put("selection_capped",capped);
        report.put("selected_count",selected.size());
        List<Map<String,Object>> functions=new ArrayList<>();report.put("functions",functions);
        report.put("analysis_complete",false);save();
        DecompInterface decompiler=new DecompInterface();
        // We consume C markup, not HighFunction's serialized syntax/data-flow tree.
        // Try omitting that unused tree after the constructor exceeded the response buffer.
        DecompileOptions options=new DecompileOptions();
        options.setMaxPayloadMBytes(64);
        decompiler.setOptions(options);
        decompiler.toggleSyntaxTree(false);
        decompiler.toggleCCode(true);
        report.put("syntax_tree_requested",false);
        report.put("decompiler_payload_limit_mib",64);
        if(!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Decompiler unavailable");
        try {
            for(Address address:selected) {
                monitor.checkCancelled();
                Map<String,Object> item=new LinkedHashMap<>();
                item.put("elf_address",address.subtract(base));functions.add(item);
                Function function=getFunctionAt(address);
                if(function==null) item.put("status","NO_FUNCTION_AT_SELECTED_ADDRESS");
                else {
                    item.put("name",function.getName());item.put("analysis_no_return",function.hasNoReturn());
                    item.put("body_address_count",function.getBody().getNumAddresses());
                    var instructions=currentProgram.getListing().getInstructions(function.getBody(),true);
                    List<Map<String,Object>> listing=new ArrayList<>();
                    while(instructions.hasNext() && listing.size()<256) {
                        var ins=instructions.next();
                        Map<String,Object> row=new LinkedHashMap<>();
                        row.put("elf_address",ins.getAddress().subtract(base));row.put("assembly",ins.toString());listing.add(row);
                    }
                    item.put("listing_prefix",listing);item.put("listing_prefix_truncated",instructions.hasNext());
                    // This original constructor exceeded 30s in run 36813678532.
                    // Increase only its budget, not every function in the batch.
                    int seconds=address.subtract(base)==0xdc8480L ? 180 : 30;
                    item.put("decompile_timeout_seconds",seconds);
                    var result=decompiler.decompileFunction(function,seconds,monitor);
                    item.put("diagnostic",result.getErrorMessage());
                    if(result.decompileCompleted() && result.getDecompiledFunction()!=null) {
                        String code=result.getDecompiledFunction().getC();
                        if(code.length()<=200000) { item.put("status","DECOMPILED_NOT_VALIDATED");item.put("c_like",code); }
                        else item.put("status","OUTPUT_LIMIT");
                    } else item.put("status","DECOMPILATION_FAILED");
                }
                report.put("processed_count",functions.size());save();
            }
            report.put("analysis_complete",true);save();
        } finally { decompiler.dispose(); }
    }
}
