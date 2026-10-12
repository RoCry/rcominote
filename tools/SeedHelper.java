// Fixed entry seeds for pinned LEOPARD adfus.bin. Static analysis only.
// @category CoMiResearch
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import java.math.BigInteger;

public class SeedHelper extends GhidraScript {
    public void run() throws Exception {
        Register thumb = currentProgram.getRegister("TMode");
        if (thumb == null) throw new IllegalStateException("Expected ARM Thumb language");
        currentProgram.getProgramContext().setValue(
            thumb, currentProgram.getMinAddress(), currentProgram.getMaxAddress(), BigInteger.ONE);
        long[] offsets = {0, 0x467c, 0x481c, 0x48ac, 0x4bcc, 0x3c08, 0x37d0,
            0x2c28, 0x3e48, 0x325c, 0x2d30, 0x4584, 0x4334, 0x774c,
            0x81b2, 0x9cf2, 0x44d0, 0xbc98, 0xbd68};
        for (long offset : offsets) {
            Address address = toAddr(0x2ff70000L + offset);
            disassemble(address);
            if (getFunctionAt(address) == null) createFunction(address, null);
        }
    }
}
