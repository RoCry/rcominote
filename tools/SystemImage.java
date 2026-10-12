// Fixed FW010004 instruction-evidenced entries. Static analysis only.
// @category CoMiResearch
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FlowOverride;
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
        0x1009ef2cL, 0x100b9652L, 0x100b96c8L,
        0x1009ffbaL, 0x1002d260L
    };

    // Bottom-up contract from actual BL chain + pinned Zephyr thread_entry.c.
    // Exclusive code ends exclude NOP padding/literals. This is a static model,
    // not a claim that a live thread termination was observed.
    private static final long[][] NO_RETURN = {
        {0x1009ffbaL, 0x1009ffceL},
        {0x1002d260L, 0x1002d2a2L},
        {0x1009aa54L, 0x1009ab0aL},
        {0x1002d0c4L, 0x1002d11eL},
        {0x1002d818L, 0x1002d84cL}
    };

    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 1 && args[0].equals("seed")) {
            Register thumb = currentProgram.getRegister("TMode");
            if (thumb == null) throw new IllegalStateException("Expected ARM Thumb language");
            currentProgram.getProgramContext().setValue(
                thumb, currentProgram.getMinAddress(), currentProgram.getMaxAddress(), BigInteger.ONE);
            for (long[] region : NO_RETURN) {
                Address address = toAddr(region[0]);
                disassemble(address);
                Function function = getFunctionAt(address);
                if (function == null) function = createFunction(address, null);
                if (function == null) throw new IllegalStateException("Cannot seed no-return entry: " + address);
                function.setBody(new AddressSet(address, toAddr(region[1] - 1)));
                function.setNoReturn(true);
                if (region[0] == 0x1009ffbaL) {
                    // This call aborts the current thread; the same abort function
                    // can return for other threads, so constrain only this site.
                    getInstructionAt(toAddr(0x1009ffcaL)).setFlowOverride(FlowOverride.CALL_RETURN);
                }
            }
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
        for (long[] region : NO_RETURN) {
            Function function = getFunctionAt(toAddr(region[0]));
            if (function == null || !function.hasNoReturn()
                    || !function.getBody().getMaxAddress().equals(toAddr(region[1] - 1))) {
                throw new IllegalStateException("No-return boundary drift: " + Long.toHexString(region[0]));
            }
        }
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
