// Fixed FW010004 instruction-evidenced entries. Static analysis only.
// @category CoMiResearch
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

public class SystemImage extends GhidraScript {
    // Existing readback reports establish these entries or direct-call targets.
    private static final long[] ENTRIES = {
        0x1000bb5cL, 0x1000bc18L, 0x1000bcecL, 0x1000bdb0L,
        0x1000c0e8L, 0x10023020L, 0x100242a8L, 0x100242b0L,
        0x10026614L, 0x10027720L, 0x1002d0c4L, 0x1002d800L,
        0x1002d818L, 0x1009aa24L, 0x1009c1d0L, 0x1009aa54L,
        0x1009ef2cL, 0x100b9652L, 0x100b96c8L
    };

    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 1 && args[0].equals("seed")) {
            Register thumb = currentProgram.getRegister("TMode");
            if (thumb == null) throw new IllegalStateException("Expected ARM Thumb language");
            currentProgram.getProgramContext().setValue(
                thumb, currentProgram.getMinAddress(), currentProgram.getMaxAddress(), BigInteger.ONE);
            for (long entry : ENTRIES) {
                Address address = toAddr(entry);
                disassemble(address);
                if (getFunctionAt(address) == null && createFunction(address, null) == null) {
                    throw new IllegalStateException("Cannot seed entry: " + Long.toHexString(entry));
                }
            }
            return;
        }
        if (args.length != 2 || !args[0].equals("export")) {
            throw new IllegalArgumentException("Expected seed or export NEW_OUTPUT_FILE");
        }
        Path output = Path.of(args[1]);
        if (Files.exists(output)) throw new IllegalArgumentException("Refusing overwrite: " + output);
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Cannot open program");
        StringBuilder report = new StringBuilder("// Static inference, not executed behavior.\n");
        try {
            for (long entry : ENTRIES) {
                Function function = getFunctionAt(toAddr(entry));
                if (function == null) throw new IllegalStateException("Missing function: " + Long.toHexString(entry));
                DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
                if (!result.decompileCompleted() || result.getDecompiledFunction() == null) {
                    throw new IllegalStateException("Decompilation failed at " + Long.toHexString(entry)
                        + ": " + result.getErrorMessage());
                }
                report.append("\n// Mapped address 0x").append(Long.toHexString(entry)).append("\n");
                report.append(result.getDecompiledFunction().getC());
            }
            Files.writeString(output, report.toString(), StandardOpenOption.CREATE_NEW);
        } finally {
            decompiler.dispose();
        }
    }
}
