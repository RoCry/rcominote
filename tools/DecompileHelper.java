// Export bounded helper functions after headless analysis. Never executes target code.
// @category CoMiResearch
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import java.nio.file.Files;
import java.nio.file.Path;

public class DecompileHelper extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("Expected new output file");
        Path output = Path.of(args[0]);
        if (Files.exists(output)) throw new IllegalArgumentException("Refusing overwrite: " + output);
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Cannot open program");
        StringBuilder report = new StringBuilder("// Static inference, not executed behavior.\n");
        long[] offsets = {0x467c, 0x481c, 0x48ac, 0x4bcc, 0x3c08, 0x37d0,
            0x2c28, 0x3e48, 0x325c, 0x2d30, 0x4584, 0x4334, 0x774c,
            0x81b2, 0x9cf2, 0x44d0, 0xbc98, 0xbd68};
        try {
            for (long offset : offsets) {
                Function function = getFunctionAt(toAddr(0x2ff70000L + offset));
                if (function == null) throw new IllegalStateException("Missing function: " + Long.toHexString(offset));
                DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
                if (!result.decompileCompleted()) throw new IllegalStateException(result.getErrorMessage());
                report.append("\n// File offset 0x").append(Long.toHexString(offset)).append("\n");
                report.append(result.getDecompiledFunction().getC());
            }
            Files.writeString(output, report.toString(), java.nio.file.StandardOpenOption.CREATE_NEW);
        } finally {
            decompiler.dispose();
        }
    }
}
