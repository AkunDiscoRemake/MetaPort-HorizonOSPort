// SPDX-License-Identifier: GPL-3.0-only
// @category MetaPort
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
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
        if(args.length!=2) throw new IllegalArgumentException("roots-file output-json");
        output=Path.of(args[1]);
        Address base=currentProgram.getImageBase();
        List<String> roots=Files.readAllLines(Path.of(args[0]));
        if(roots.isEmpty() || roots.size()>32) throw new IllegalArgumentException("Root budget");
        LinkedHashSet<Address> selected=new LinkedHashSet<>();
        for(String root:roots) selected.add(base.add(Long.parseUnsignedLong(root.trim(),16)));
        report.put("program_sha256",currentProgram.getExecutableSHA256());
        report.put("image_base",base.toString());
        report.put("root_count",selected.size());
        report.put("function_cap",96);
        report.put("identified_function_count_not_total_original",currentProgram.getFunctionManager().getFunctionCount());
        report.put("scope","At most two Ghidra called-function levels; indirect targets unresolved; analyzer prototypes may be wrong");
        report.put("firmware_executed",false);
        report.put("private_abi_validated",false);
        report.put("all_horizon_disassembled",false);
        List<Map<String,Object>> frontier=new ArrayList<>();
        List<Address> level=new ArrayList<>(selected);
        boolean capped=false;
        for(int depth=0;depth<2 && selected.size()<96;depth++) {
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
                if(selected.size()==96) { capped=true;continue; }
                selected.add(a);next.add(a);
            }
            level=next;
        }
        report.put("frontier",frontier);report.put("selection_capped",capped);
        report.put("selected_count",selected.size());
        List<Map<String,Object>> functions=new ArrayList<>();report.put("functions",functions);
        report.put("analysis_complete",false);save();
        DecompInterface decompiler=new DecompInterface();
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
                    var result=decompiler.decompileFunction(function,30,monitor);
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
