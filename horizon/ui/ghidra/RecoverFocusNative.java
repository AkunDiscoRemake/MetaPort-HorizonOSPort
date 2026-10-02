// SPDX-License-Identifier: GPL-3.0-only
// @category MetaPort
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.program.model.listing.Function;
import com.google.gson.GsonBuilder;
import java.nio.file.*;
import java.util.*;

/** Analyze original focus policy/IPC functions; never instantiate or execute the daemon. */
public class RecoverFocusNative extends GhidraScript {
    private final Map<String,Object> report = new LinkedHashMap<>();
    private Path output;
    private void save() throws Exception {
        Path temp=output.resolveSibling(output.getFileName()+".tmp");
        Files.writeString(temp,new GsonBuilder().setPrettyPrinting().create().toJson(report));
        Files.move(temp,output,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException("output-json expected-sha256");
        if(!args[1].equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalArgumentException("Wrong pinned focus program");
        output=Path.of(args[0]);
        report.put("program_sha256",currentProgram.getExecutableSHA256());
        report.put("firmware_executed",false);
        report.put("private_abi_validated",false);
        report.put("service_implemented",false);
        report.put("scope","Ghidra inferred functions/prototypes, not original source or validated recompilation; indirect calls remain unresolved");
        List<Function> functions=new ArrayList<>();
        var iterator=currentProgram.getFunctionManager().getFunctions(true);
        while(iterator.hasNext()) {
            Function f=iterator.next();
            var block=currentProgram.getMemory().getBlock(f.getEntryPoint());
            if(!f.isExternal() && !f.isThunk() && block!=null && block.isExecute()) functions.add(f);
        }
        report.put("identified_function_count",functions.size());
        report.put("function_cap",512);
        report.put("analysis_complete",false);
        List<Map<String,Object>> rows=new ArrayList<>();report.put("functions",rows);save();
        DecompInterface decompiler=new DecompInterface();
        DecompileOptions options=new DecompileOptions();options.setMaxPayloadMBytes(32);
        decompiler.setOptions(options);decompiler.toggleCCode(true);decompiler.toggleSyntaxTree(false);
        if(!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Decompiler open failed");
        long deadline=System.nanoTime()+900_000_000_000L;int characters=0;
        try {
            for(Function f:functions) {
                monitor.checkCancelled();
                if(rows.size()>=512 || System.nanoTime()>deadline || characters>=12*1024*1024) break;
                Map<String,Object> row=new LinkedHashMap<>();rows.add(row);
                row.put("elf_address",f.getEntryPoint().subtract(currentProgram.getImageBase()));
                row.put("name",f.getName());row.put("signature",f.getSignature().toString());
                List<String> calls=new ArrayList<>();
                for(Function target:f.getCalledFunctions(monitor)) calls.add(target.getName());
                Collections.sort(calls);row.put("identified_calls",calls);
                var result=decompiler.decompileFunction(f,15,monitor);
                if(result.decompileCompleted() && result.getDecompiledFunction()!=null) {
                    String code=result.getDecompiledFunction().getC();
                    if(code.length()<=256*1024 && characters+code.length()<=12*1024*1024) {
                        row.put("status","DECOMPILED_NOT_VALIDATED");row.put("c",code);characters+=code.length();
                    } else row.put("status","SOURCE_TEXT_BUDGET");
                } else {
                    row.put("status","DECOMPILE_FAILED");row.put("error",result.getErrorMessage());
                }
                report.put("processed_count",rows.size());save();
            }
            report.put("analysis_complete",rows.size()==functions.size());
            report.put("all_identified_functions_decompiled",rows.size()==functions.size() &&
                rows.stream().allMatch(r -> "DECOMPILED_NOT_VALIDATED".equals(r.get("status"))));
            save();
        } finally { decompiler.dispose(); }
    }
}
