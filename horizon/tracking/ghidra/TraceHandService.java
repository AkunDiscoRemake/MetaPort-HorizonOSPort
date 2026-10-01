// SPDX-License-Identifier: GPL-3.0-only
// @category MetaPort
// Shared service scheduler callers, not hand-exclusive or runtime activation.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public class TraceHandService extends GhidraScript {
    private static final String SHA="a6474bc3710558a26827a5165556a99cd998b013233072eefe4edf2b6b2f1945";
    private static final Set<String> NAMES=Set.of("setpriority", "sched_setscheduler",
        "sched_setparam", "sched_setattr", "sched_setaffinity", "pthread_setschedparam",
        "pthread_setschedprio", "androidSetThreadPriority", "SetTaskProfiles",
        "set_sched_policy", "set_cpuset_policy");
    private final Map<Address,Function> roots=new LinkedHashMap<>();
    private void consider(Function f) {
        if(!NAMES.contains(f.getName())) return;
        roots.put(f.getEntryPoint(),f);
        Address[] thunks=f.getFunctionThunkAddresses(true);
        if(thunks!=null) for(Address address:thunks) {
            Function thunk=getFunctionAt(address);
            if(thunk!=null) roots.put(address,thunk);
        }
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException("functions.txt output.json");
        if(!SHA.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("Wrong original tracking service");
        Path functions=Path.of(args[0]);Address base=currentProgram.getImageBase();
        Set<Long> selected=new LinkedHashSet<>();
        for(String line:Files.readAllLines(functions)) if(!line.isBlank())
            selected.add(Long.parseUnsignedLong(line.trim(),16));
        if(selected.size()>24) throw new IllegalArgumentException("Function budget");
        // Prioritize the next measured frontier, not the same imported thunks.
        // These wrappers/factory were recovered in run 36795978696. ELF VAs only.
        for(long elf:new long[]{0x1b5ddcL,0x4df130L,0x4df3fcL,0x4df474L,0x4df570L,
                               0x4df1acL,0x4df4e0L}) {
            Function f=getFunctionAt(base.add(elf));
            if(f!=null) roots.put(f.getEntryPoint(),f);
        }
        var internal=currentProgram.getFunctionManager().getFunctions(true);
        while(internal.hasNext()) {monitor.checkCancelled();consider(internal.next());}
        var external=currentProgram.getFunctionManager().getExternalFunctions();
        while(external.hasNext()) {monitor.checkCancelled();consider(external.next());}
        List<Map<String,Object>> evidence=new ArrayList<>();
        for(Function root:roots.values()) {
            monitor.checkCancelled();var refs=getReferencesTo(root.getEntryPoint());
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("name",root.getName());row.put("address",root.getEntryPoint().toString());
            row.put("external",root.isExternal());row.put("reference_count",refs.length);
            List<Map<String,Object>> callers=new ArrayList<>();Set<Long> added=new LinkedHashSet<>();
            for(int i=0;i<Math.min(refs.length,128);i++) {
                var ref=refs[i];
                if(!ref.getReferenceType().isCall()) continue;
                Function caller=getFunctionContaining(ref.getFromAddress());
                if(caller==null || caller.isExternal()) continue;
                long address=caller.getEntryPoint().subtract(base);
                if(!caller.isThunk() && added.size()<2 && selected.size()<24 && selected.add(address)) added.add(address);
                Map<String,Object> call=new LinkedHashMap<>();
                call.put("caller_name",caller.getName());call.put("caller_elf_address",address);
                call.put("callsite_elf_address",ref.getFromAddress().subtract(base));
                call.put("caller_is_thunk",caller.isThunk());
                call.put("selected",selected.contains(address));callers.add(call);
            }
            row.put("callers",callers);row.put("references_truncated",refs.length>128);evidence.add(row);
        }
        // Selection can grow after a root is visited; report final membership.
        for(var row:evidence) {
            @SuppressWarnings("unchecked")
            var calls=(List<Map<String,Object>>)row.get("callers");
            int omitted=0;
            for(var call:calls) {
                boolean included=selected.contains((Long)call.get("caller_elf_address"));
                call.put("selected",included);
                if(!included && !Boolean.TRUE.equals(call.get("caller_is_thunk"))) omitted++;
            }
            row.put("unselected_non_thunk_callsite_count",omitted);
        }
        StringBuilder text=new StringBuilder();
        for(long address:selected) text.append(Long.toHexString(address)).append('\n');
        Files.writeString(functions,text.toString());
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("program_sha256",SHA);report.put("roots",evidence);
        // 16-byte literal loaded by the Realtime sched_attr branch at 005df268.
        // Raw bytes only: do not guess FIFO/RR or flags from the name Realtime.
        byte[] literal=new byte[16];Address literalAddress=base.add(0x72840L);
        if(currentProgram.getMemory().getBytes(literalAddress,literal)!=literal.length)
            throw new IllegalStateException("Incomplete scheduler literal");
        Map<String,Object> constant=new LinkedHashMap<>();
        constant.put("elf_address",0x72840L);
        constant.put("bytes_hex",HexFormat.of().formatHex(literal));
        report.put("realtime_header_literal",constant);

        report.put("selected_elf_addresses",new ArrayList<>(selected));
        report.put("firmware_executed",false);report.put("hand_exclusive",false);
        report.put("scope","Named scheduler/profile functions and thunks, direct call refs only; 128 refs/root, 2 new callers/root, 24 total targets. Indirect dispatch and raw syscall numbers unresolved.");
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
