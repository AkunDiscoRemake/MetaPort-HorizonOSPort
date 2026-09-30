// SPDX-License-Identifier: GPL-3.0-only
// Original MetaPort analysis tooling; output remains third-party-derived evidence.
// @category MetaPort
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.pcode.PcodeOp;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParser;
import com.google.gson.JsonElement;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public class DecompileHandInput extends GhidraScript {
    private static final String ENGINE_SHA="10eac37188c97389dabfe7599a354d146d1e6223d849546d230796af93418ffe";
    private final Map<Address,String> selected=new LinkedHashMap<>();
    private void select(Function function,String reason) {
        if(function!=null && !function.isExternal() && selected.size()<32)
            selected.putIfAbsent(function.getEntryPoint(),reason);
    }
    private Function discover(Address address) throws Exception {
        var block=currentProgram.getMemory().getBlock(address);
        if(block==null || !block.isExecute() || (address.getOffset()&3)!=0) return null;
        Function function=getFunctionAt(address);
        if(function==null && getFunctionContaining(address)==null) {
            // Static disassembly only; never invoke the pointed-to code.
            disassemble(address);function=createFunction(address,null);
        }
        return function;
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException("input-strings.json output.json");
        if(!ENGINE_SHA.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("Pinned input/vtable addresses require the exact engine hash");
        Address base=currentProgram.getImageBase();
        // Constructors previously observed in hand-decompilation.json. ELF VAs,
        // NOT Ghidra's relocated addresses or an invented C++ object layout.
        select(discover(base.add(0x1620ce0L)),"Observed model-executor construction");
        select(discover(base.add(0x16222a0L)),"Observed DPE attribute consumer");
        // Direct callees named in the previously recovered FUN_0172bee0 C-like
        // output. Selection evidence only: no assumed signature or live call.
        // These are ELF VAs after subtracting the observed 0x100000 image base.
        for(long address:new long[]{0x1654a90L,0x16556c0L,0xa9c4e0L,
                                    0x8a6600L,0x6d4dc0L,0x164fd20L,0xe6a5d0L})
            select(discover(base.add(address)),
                   "Observed FUN_0172bee0 pseudo-C callee; call edge and ABI unvalidated");
        // Next layer, selected from the measured 18-function report. Still not
        // private signatures: inspect tensor construction and output tree packing.
        for(long address:new long[]{0x8a67c0L,0x248d37cL,0x1651ca0L})
            select(discover(base.add(address)),"Observed tensor/visual-output helper in prior callee C-like evidence");
        List<Map<String,Object>> tables=new ArrayList<>();
        // Constructor assigns these address points to its two interfaces.
        // Read adjacent slots only as evidence, never as a callable ABI.
        for(long table:new long[]{0x268b708L,0x268b758L}) {
            for(int index=0;index<12;index++) {
                monitor.checkCancelled();
                Address slot=base.add(table+index*8L);
                Map<String,Object> row=new LinkedHashMap<>();
                row.put("address_point_elf",table);row.put("slot_offset",index*8);
                row.put("raw_pointer_hex",Long.toUnsignedString(currentProgram.getMemory().getLong(slot),16));
                List<Map<String,Object>> refs=new ArrayList<>();
                for(Reference reference:getReferencesFrom(slot)) {
                    Address to=reference.getToAddress();
                    Function function=getFunctionAt(to);
                    Map<String,Object> target=new LinkedHashMap<>();
                    target.put("ghidra_address",to.toString());
                    target.put("reference_type",reference.getReferenceType().toString());
                    target.put("function",function==null?null:function.getName());refs.add(target);
                    select(function,"Pointer reference at observed address point 0x"+Long.toHexString(table)+" + "+index*8);
                }
                // Some headless analyses leave no DataReference at a vtable slot.
                // Read the pointer from Ghidra's already-relocated memory, not
                // from the ELF file. Do NOT add imageBase a second time.
                long pointer=currentProgram.getMemory().getLong(slot);
                Address candidate=toAddr(pointer);
                Function pointed=discover(candidate);
                row.put("relocated_memory_candidate",candidate.toString());
                row.put("candidate_function",pointed==null?null:pointed.getName());
                row.put("candidate_abi_validated",false);
                select(pointed,"Executable pointer candidate in relocated memory at 0x"+
                       Long.toHexString(table)+" + "+index*8+"; not a validated ABI");
                row.put("references",refs);tables.add(row);
            }
        }
        var strings=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        if(strings.size()>128) throw new IllegalArgumentException("String budget");
        List<Map<String,Object>> stringEvidence=new ArrayList<>();
        for(JsonElement element:strings) {
            monitor.checkCancelled();
            var target=element.getAsJsonObject();
            Address address=base.add(target.get("address").getAsLong());
            String text=target.get("text").getAsString();
            if(text.length()>512) throw new IllegalArgumentException("String length budget");
            Map<String,Object> row=new LinkedHashMap<>();row.put("text",text);
            row.put("elf_address",target.get("address").getAsLong());
            List<String> refs=new ArrayList<>();
            for(Reference reference:getReferencesTo(address)) {
                if(refs.size()>=64) break;
                refs.add(reference.getFromAddress().toString());
                select(getFunctionContaining(reference.getFromAddress()),"Direct input-metadata string reference: "+text);
            }
            row.put("references",refs);stringEvidence.add(row);
        }
        DecompInterface decompiler=new DecompInterface();
        List<Map<String,Object>> functions=new ArrayList<>();
        try {
            if(!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Open program failed");
            for(var candidate:selected.entrySet()) {
                monitor.checkCancelled();Function function=getFunctionAt(candidate.getKey());
                Map<String,Object> row=new LinkedHashMap<>();
                row.put("ghidra_address",candidate.getKey().toString());
                row.put("elf_address",candidate.getKey().subtract(base));
                row.put("name",function.getName());row.put("selection_evidence",candidate.getValue());
                DecompileResults result=decompiler.decompileFunction(function,30,monitor);
                row.put("diagnostic",result.getErrorMessage());
                if(result.decompileCompleted() && result.getDecompiledFunction()!=null) {
                    String code=result.getDecompiledFunction().getC();
                    if(code.length()<=200000) {row.put("status","DECOMPILED_NOT_VALIDATED");row.put("c_like",code);}
                    else row.put("status","OUTPUT_LIMIT");
                } else row.put("status","DECOMPILATION_FAILED");
                // Listing-level bodies may be incomplete after bounded analysis.
                // Preserve independent decompiler P-code evidence instead of
                // interpreting an empty listing call sample as absence of calls.
                List<Map<String,Object>> pcodeCalls=new ArrayList<>();int pcodeVisited=0;
                boolean pcodeTruncated=false;
                if(result.getHighFunction()!=null) {
                    var ops=result.getHighFunction().getPcodeOps();
                    while(ops.hasNext() && pcodeVisited<50000 && pcodeCalls.size()<256) {
                        var op=ops.next();pcodeVisited++;
                        if(op.getOpcode()!=PcodeOp.CALL && op.getOpcode()!=PcodeOp.CALLIND) continue;
                        Map<String,Object> call=new LinkedHashMap<>();
                        call.put("ghidra_address",op.getSeqnum().getTarget().toString());
                        call.put("computed",op.getOpcode()==PcodeOp.CALLIND);
                        if(op.getOpcode()==PcodeOp.CALL && op.getNumInputs()>0)
                            call.put("target_varnode",op.getInput(0).toString());
                        pcodeCalls.add(call);
                    }
                    pcodeTruncated=ops.hasNext();
                }
                row.put("pcode_available",result.getHighFunction()!=null);
                row.put("pcode_ops_visited",pcodeVisited);
                row.put("pcode_call_sites_sample",pcodeCalls);
                row.put("pcode_scan_truncated",pcodeTruncated);
                row.put("listing_body_address_count",function.getBody().getNumAddresses());
                List<Map<String,Object>> listingSample=new ArrayList<>();
                List<Map<String,Object>> calls=new ArrayList<>();int visited=0;
                var instructions=currentProgram.getListing().getInstructions(function.getBody(),true);
                while(instructions.hasNext() && visited<20000 && calls.size()<256) {
                    Instruction instruction=instructions.next();visited++;
                    if(listingSample.size()<16) {
                        Map<String,Object> sample=new LinkedHashMap<>();
                        sample.put("ghidra_address",instruction.getAddress().toString());
                        sample.put("mnemonic",instruction.getMnemonicString());
                        sample.put("flow_type",instruction.getFlowType().toString());
                        listingSample.add(sample);
                    }
                    if(!instruction.getFlowType().isCall()) continue;
                    Map<String,Object> call=new LinkedHashMap<>();
                    call.put("elf_address",instruction.getAddress().subtract(base));
                    call.put("computed",instruction.getFlowType().isComputed());
                    List<String> destinations=new ArrayList<>();
                    for(Reference ref:instruction.getReferencesFrom())
                        if(ref.getReferenceType().isCall()) destinations.add(ref.getToAddress().toString());
                    call.put("ghidra_destinations",destinations);calls.add(call);
                }
                row.put("listing_instructions_visited",visited);
                row.put("listing_instruction_sample",listingSample);
                row.put("listing_scan_truncated",instructions.hasNext());
                row.put("call_sites_sample",calls);functions.add(row);
            }
        } finally {decompiler.dispose();}
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("program_sha256",ENGINE_SHA);report.put("image_base",base.toString());
        report.put("tool","Ghidra 11.3.2");report.put("firmware_executed",false);
        report.put("abi_validated",false);report.put("input_conversion_ported",false);
        report.put("scope","At most 32 functions; pointer windows may cross vtable boundaries; indirect calls unresolved");
        report.put("pointer_windows",tables);report.put("string_references",stringEvidence);
        report.put("functions",functions);
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
