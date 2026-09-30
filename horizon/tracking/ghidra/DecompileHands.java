// C-like reconstruction of exported registry and hand-string cross-reference functions.
// Types and signatures remain inferred, NOT ABI declarations or runtime validation.
// @category MetaPort
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParser;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class DecompileHands extends GhidraScript {
    private final Map<Address,String> selected=new LinkedHashMap<>();
    private final List<Map<String,Object>> evidence=new ArrayList<>();
    private void selectReference(Reference ref, String reason) {
        Function function=getFunctionContaining(ref.getFromAddress());
        if(function!=null && !function.isExternal() && selected.size()<24) {
            selected.putIfAbsent(function.getEntryPoint(),reason);
        }
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=3) throw new IllegalArgumentException("addresses-file strings-json output-json");
        List<String> exports=Files.readAllLines(Path.of(args[0]));
        if(exports.size()>24) throw new IllegalArgumentException("Export limit");
        // Android ET_DYN symbols/rodata use base-zero ELF VAs; Ghidra rebases the import.
        Address imageBase=currentProgram.getImageBase();
        for(String text:exports) if(!text.isBlank()) {
            Address address=imageBase.add(Long.parseUnsignedLong(text.trim(),16));
            selected.put(address,"Defined dynamic export; ELF VA 0x"+text);
        }
        var strings=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonArray();
        if(strings.size()>256) throw new IllegalArgumentException("String limit");
        for(JsonElement element:strings) {
            monitor.checkCancelled();
            JsonObject target=element.getAsJsonObject();
            Address address=imageBase.add(target.get("address").getAsLong());
            String text=target.get("text").getAsString();
            Reference[] refs=getReferencesTo(address);
            Map<String,Object> item=new LinkedHashMap<>();
            item.put("elf_address",target.get("address").getAsLong());
            item.put("text",text);item.put("direct_reference_count",refs.length);
            List<String> from=new ArrayList<>();
            for(Reference ref:refs) {
                if(from.size()<16) from.add(ref.getFromAddress().toString());
                selectReference(ref,"Direct reference to string: "+text);
                if(getFunctionContaining(ref.getFromAddress())==null) {
                    // Constant/vtable indirection: evidence, not proof of a callable signature.
                    int count=0;
                    for(Reference indirect:getReferencesTo(ref.getFromAddress())) {
                        if(count++>=32) break;
                        selectReference(indirect,"Indirect reference to string: "+text);
                    }
                }
            }
            item.put("reference_addresses",from);evidence.add(item);
        }
        DecompInterface decompiler=new DecompInterface();
        List<Map<String,Object>> results=new ArrayList<>();
        try {
            if(!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Cannot open program");
            for(var candidate:selected.entrySet()) {
                monitor.checkCancelled();
                Function function=getFunctionAt(candidate.getKey());
                Map<String,Object> item=new LinkedHashMap<>();
                item.put("ghidra_address",candidate.getKey().toString());
                item.put("elf_address",candidate.getKey().subtract(imageBase));
                item.put("selection_evidence",candidate.getValue());
                if(function==null) item.put("status","NO_FUNCTION_AT_SELECTED_ADDRESS");
                else {
                    item.put("name",function.getName());
                    DecompileResults result=decompiler.decompileFunction(function,30,monitor);
                    item.put("diagnostic",result.getErrorMessage());
                    if(result.decompileCompleted() && result.getDecompiledFunction()!=null) {
                        String code=result.getDecompiledFunction().getC();
                        if(code.length()<=200000) {
                            item.put("status","DECOMPILED_NOT_VALIDATED");item.put("c_like",code);
                        } else item.put("status","OUTPUT_LIMIT");
                    } else item.put("status","DECOMPILATION_FAILED");
                }
                results.add(item);
            }
        } finally { decompiler.dispose(); }
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("tool","Ghidra 11.3.2");
        report.put("scope","At most 24 registry/string-reference functions; not complete hand algorithm recovery");
        report.put("image_base",imageBase.toString());
        report.put("program_sha256",currentProgram.getExecutableSHA256());
        report.put("firmware_executed",false);report.put("original_source_recovered",false);
        report.put("selection_status",selected.isEmpty()?"NO_FUNCTIONS_SELECTED":"SELECTED");
        report.put("string_references",evidence);report.put("functions",results);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
