// Targeted C-like reconstruction, not original source and not runtime validation.
// @category MetaPort
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class DecompileHands extends GhidraScript {
    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("addresses-file output-json");
        List<String> addresses = Files.readAllLines(Path.of(args[0]));
        if (addresses.size() > 24) throw new IllegalArgumentException("Function limit");
        DecompInterface decompiler = new DecompInterface();
        List<Map<String, Object>> results = new ArrayList<>();
        try {
            if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Cannot open program");
            for (String text : addresses) {
                if (text.isBlank()) continue;
                monitor.checkCancelled();
                Address address = toAddr(Long.parseUnsignedLong(text.trim(), 16));
                Function function = getFunctionAt(address);
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("address", text);
                if (function == null) {
                    item.put("status", "NO_FUNCTION_AT_SELECTED_ADDRESS");
                } else {
                    item.put("name", function.getName());
                    DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
                    item.put("diagnostic", result.getErrorMessage());
                    if (result.decompileCompleted() && result.getDecompiledFunction() != null) {
                        String code = result.getDecompiledFunction().getC();
                        if (code.length() <= 200000) {
                            item.put("status", "DECOMPILED_NOT_VALIDATED");
                            item.put("c_like", code);
                        } else item.put("status", "OUTPUT_LIMIT");
                    } else item.put("status", "DECOMPILATION_FAILED");
                }
                results.add(item);
            }
        } finally { decompiler.dispose(); }
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("tool", "Ghidra 11.3.2");
        report.put("scope", "At most 24 selected exported hand/gesture/skeleton functions; not full library recovery");
        report.put("program_sha256", currentProgram.getExecutableSHA256());
        report.put("firmware_executed", false);
        report.put("original_source_recovered", false);
        report.put("functions", results);
        Files.writeString(Path.of(args[1]), new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
