// SPDX-License-Identifier: GPL-3.0-only
// @category MetaPort
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Records direct CALL edges and unresolved indirect calls. Not an ABI bridge. */
public class TraceShellEntrypoints extends GhidraScript {
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=3) throw new IllegalArgumentException("seeds addresses-out report-out");
        Address base=currentProgram.getImageBase();
        List<String> lines=Files.readAllLines(Path.of(args[0]));
        if(lines.size()>8) throw new IllegalArgumentException("Seed limit");
        LinkedHashSet<Address> selected=new LinkedHashSet<>();
        List<Map<String,Object>> roots=new ArrayList<>();
        List<List<Address>> candidates=new ArrayList<>();
        for(String line:lines) {
            if(line.isBlank()) continue;
            Address address=base.add(Long.parseUnsignedLong(line.trim(),16));
            selected.add(address);
            Function f=getFunctionAt(address);
            Map<String,Object> root=new LinkedHashMap<>();
            root.put("elf_address",address.subtract(base));
            List<Map<String,Object>> calls=new ArrayList<>();
            List<Address> targets=new ArrayList<>();
            root.put("function_found",f!=null);
            int seen=0;
            if(f!=null) {
                root.put("name",f.getName());
                var instructions=currentProgram.getListing().getInstructions(f.getBody(),true);
                while(instructions.hasNext()) {
                    monitor.checkCancelled();
                    var ins=instructions.next();
                    if(!ins.getFlowType().isCall()) continue;
                    seen++;
                    if(calls.size()>=128) continue;
                    Map<String,Object> call=new LinkedHashMap<>();
                    call.put("elf_address",ins.getAddress().subtract(base));
                    call.put("instruction",ins.toString());
                    List<Map<String,Object>> edges=new ArrayList<>();
                    for(Address to:ins.getFlows()) {
                        Function target=getFunctionAt(to);
                        Map<String,Object> edge=new LinkedHashMap<>();
                        edge.put("address",to.toString());
                        edge.put("name",target==null?null:target.getName());
                        boolean eligible=target!=null && !target.isExternal() && !target.isThunk()
                            && currentProgram.getMemory().getBlock(to)!=null
                            && currentProgram.getMemory().getBlock(to).isExecute();
                        edge.put("eligible_local_body",eligible);edges.add(edge);
                        if(eligible && !targets.contains(to)) targets.add(to);
                    }
                    call.put("targets",edges);call.put("unresolved",edges.isEmpty());calls.add(call);
                }
            }
            root.put("call_instructions",seen);root.put("calls_truncated",seen>calls.size());
            root.put("calls",calls);roots.add(root);candidates.add(targets);
        }
        // Fair round-robin: nativeInit must not displace all lifecycle/passthrough helpers.
        for(int rank=0;rank<128 && selected.size()<24;rank++)
            for(List<Address> list:candidates)
                if(rank<list.size() && selected.size()<24) selected.add(list.get(rank));
        StringBuilder out=new StringBuilder();
        for(Address a:selected) out.append(Long.toHexString(a.subtract(base))).append('\n');
        Files.writeString(Path.of(args[1]),out.toString());
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("program_sha256",currentProgram.getExecutableSHA256());
        report.put("scope","One-hop direct CALL frontier only; excludes unresolved indirect calls and tail jumps");
        report.put("roots",roots);report.put("selected_functions",selected.size());
        report.put("selection_cap",24);report.put("firmware_executed",false);
        report.put("jni_abi_validated",false);report.put("surface_lifecycle_ported",false);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
