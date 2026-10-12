"""Fixed read sets derived from captured instructions; not arbitrary address access."""


def flushed_reads(blocks: tuple) -> list[str]:
    """Bound bursts; help flushes the firmware's short-output buffer after each batch."""
    commands = []
    for offset in range(0, len(blocks), 4):
        commands.extend(f"dbg mdb {b[0]:x} {b[1]:x}" for b in blocks[offset : offset + 4])
        commands.append("help")
    return commands


def flushed_phases(phases: tuple) -> list[str]:
    return [command for phase in phases for command in flushed_reads(phase)]


# Lengths are hexadecimal in the device's mdb commands; decimal here.
BLOCKS = (
    (0x1000BF20, 16, "logsrv entry", True),
    (0x1000C0AC, 8, "two PC-relative literals", False),
    (0x100C26BA, 13, "r1 string candidate", False),
    (0x100AD486, 16, "BL target and adjacent instructions", True),
    (0x1000BF30, 16, "BL return and subsequent instructions", True),
)

VENDOR_BLOCKS = (
    (0x1000A01C, 16, "vendor_read observed thread entry", True),
    (0x10009E9C, 16, "vendor observed thread entry", True),
    (0x1000A170, 16, "vendor_read first four PC-relative literals", False),
    (0x1000A180, 4, "vendor_read r7 PC-relative literal", False),
    (0x1000A1AC, 4, "vendor_read r8 PC-relative literal", False),
    # Contiguous executable span from observed entry up to its first evidenced
    # literal pool. Function boundaries within the span remain inferred.
    *(
        (address, min(16, 0x1000A170 - address), "vendor_read code before literal pool", True)
        for address in range(0x1000A02C, 0x1000A170, 16)
    ),
)

HANDLER_CORE_BLOCKS = (
    (0x1000A01C, 16, "vendor_read entry prerequisite", True),
    (0x1000A14C, 16, "direct BL to packet-processing callee", True),
    (0x1000B3B4, 16, "packet-processing callee entry", True),
    (0x1000B3C4, 16, "packet-processing callee continuation", True),
    *(
        (address, min(16, 0x1000B558 - address), "callee span before evidenced literal pool", True)
        for address in range(0x1000B3D4, 0x1000B558, 16)
    ),
    (0x1000B558, 12, "three callee PC-relative literals", False),
)
SPECIAL_BLOCKS = (
    (0x1000B0C0, 16, "command 0x3a direct callee entry", True),
    (0x1000B0D0, 16, "command 0x3a callee continuation", True),
    (0x1000B0E0, 16, "command 0x3a after observed BL return", True),
    (0x1000B0F0, 16, "command 0x3a continuation", True),
    (0x1000B100, 16, "command 0x3a final branch targets", True),
    (0x1000B110, 4, "command 0x3a r0 PC-relative literal", False),
    (0x100C22BB, 16, "command 0x3a r0 literal target prefix", False),
    (0x100AD3D6, 16, "command 0x3a direct helper callee", True),
)
HANDLER_BLOCKS = (*HANDLER_CORE_BLOCKS, *SPECIAL_BLOCKS)

INFO_BODY_BLOCKS = (
    *(
        (address, 16, "previously decoded call/table prerequisite", False)
        for address in (
            0x1000A01C,
            0x1000A14C,
            0x1000B3B4,
            0x1000B3C4,
            0x1000B404,
            0x1000B414,
            0x1000B474,
        )
    ),
    (0x1000AAD0, 16, "GET_DEVICE_INFO callee entry", True),
    (0x1000AAE0, 16, "GET_DEVICE_INFO callee continuation", True),
    *(
        (address, min(16, 0x1000ABE4 - address), "GET_DEVICE_INFO code before literal pool", True)
        for address in range(0x1000AAF0, 0x1000ABE4, 16)
    ),
    (0x1000ABE4, 16, "GET_DEVICE_INFO literal pool", False),
)
INFO_REFERENCES = (
    (0x100BA780, 3, "version bytes referenced by GET_DEVICE_INFO", False),
    (0x100C1243, 8, "capacity getter r0 literal prefix", False),
    (0x100C21E8, 10, "model string referenced by GET_DEVICE_INFO", False),
    (0x100549C0, 16, "first capacity getter entry", True),
    (0x100549D0, 16, "first capacity getter continuation", True),
    (0x10054A28, 16, "second capacity getter entry", True),
    (0x10054A38, 16, "second capacity getter continuation", True),
)
INFO_CAPACITY = (
    *(
        (address, min(16, 0x10054A18 - address), "free-capacity getter continuation", True)
        for address in range(0x100549E0, 0x10054A18, 16)
    ),
    *(
        (address, min(16, 0x10054A80 - address), "total-capacity getter continuation", True)
        for address in range(0x10054A48, 0x10054A80, 16)
    ),
)
INFO_STORAGE_ENTRY = (
    (0x100546FC, 16, "capacity getter volume-check BL target", True),
    (0x1005470C, 16, "volume-check callee continuation", True),
    (0x1002F24C, 16, "capacity getter stat-query BL target", True),
    (0x1002F25C, 16, "stat-query callee continuation", True),
)
INFO_STORAGE_MORE = (
    (0x1005471C, 16, "volume-check taken branch", True),
    (0x1005472C, 12, "volume-check return before referenced literals", True),
    (0x10054738, 8, "volume-check PC-relative literals", False),
    (0x1002F26C, 16, "stat-query branch continuation", True),
    (0x1002F27C, 16, "stat-query path checks", True),
    *(
        (address, 16, "stat-query continuation before literal pool", True)
        for address in range(0x1002F28C, 0x1002F2DC, 16)
    ),
    (0x1002F2DC, 12, "stat-query first three PC-relative literals", False),
)
INFO_STORAGE_TABLE = (
    (0x100BCE24, 16, "volume-name pointer table first four entries", False),
    (0x100BCE34, 4, "volume-name pointer table fifth entry", False),
)
INFO_STORAGE_VOLUME = (
    (0x18017BD0, 8, "SD volume entry: code-proven base plus index four times stride eight", False),
)
INFO_STORAGE_MOUNT = (
    (0x18010A64, 16, "SD mount candidate first fields", False),
    (0x18010A74, 16, "SD mount candidate through code-proven vtable offset", False),
)
INFO_STORAGE_VTABLE = ((0x100BC0E0, 4, "mounted SD statvfs callback pointer", False),)
INFO_STORAGE_CALLBACK = (
    (0x100A42D6, 16, "SD statvfs callback Thumb entry", True),
    (0x100A42E6, 16, "SD statvfs callback entry continuation", True),
)
INFO_STORAGE_CALLBACK_TAIL = ((0x100A42F6, 16, "SD statvfs success continuation and error branch", True),)
INFO_STORAGE = (
    *INFO_STORAGE_ENTRY,
    *INFO_STORAGE_MORE,
    *INFO_STORAGE_TABLE,
    *INFO_STORAGE_VOLUME,
    *INFO_STORAGE_MOUNT,
    *INFO_STORAGE_VTABLE,
    *INFO_STORAGE_CALLBACK,
    *INFO_STORAGE_CALLBACK_TAIL,
)
INFO_BLOCKS = (*INFO_BODY_BLOCKS, *INFO_REFERENCES, *INFO_CAPACITY)
DISK_ENTRY = (
    (0x100A4306, 2, "statvfs error-path return branch", True),
    (0x100A794E, 16, "statvfs direct free-cluster callee", True),
    (0x100A795E, 16, "free-cluster callee continuation", True),
)
DISK_MORE = (
    (0x100A796E, 16, "free-cluster cached-count checks", True),
    (0x1003F684, 16, "free-cluster volume lookup direct callee", True),
    (0x1003F694, 16, "volume lookup callee continuation", True),
)
DISK_VOLUME_BODY = (
    *(
        (address, 16, "volume lookup mounted-drive path", True)
        for address in range(0x1003F6A4, 0x1003F6E4, 16)
    ),
    (0x1003F864, 4, "volume lookup indexed filesystem-table literal", False),
)
DISK_STATUS_ENTRY = (
    (0x10040D9C, 16, "mounted-drive status direct callee", True),
    (0x10040DAC, 16, "disk status continuation", True),
)
DISK_STATUS_MORE = (
    (0x10040DBC, 4, "disk-status final return before literals", True),
    (0x10040DC0, 8, "disk-name table and status-translation literals", False),
    (0x100A1998, 16, "named-disk status direct callee", True),
    (0x100A19A8, 16, "named-disk status continuation", True),
)
DISK_REGISTRY_ENTRY = (
    (0x10025870, 16, "named-disk registry lookup callee", True),
    (0x10025880, 16, "registry lookup continuation", True),
)
DISK_TABLES = (
    (0x100BC768, 16, "disk-status name table first four entries", False),
    (0x100BC778, 4, "disk-status name table fifth entry", False),
    (0x1800FD4C, 16, "FatFs pointer table first four candidate entries", False),
    (0x1800FD5C, 4, "FatFs pointer table fifth candidate entry", False),
)
DISK_REGISTRY_BODY = (
    *(
        (address, min(16, 0x100258C4 - address), "registry lookup remaining branches", True)
        for address in range(0x10025890, 0x100258C4, 16)
    ),
    (0x100258C4, 8, "registry list-head and mutex literals", False),
)
DISK_FS = (
    (0x100C6F54, 3, "disk-name table fifth string", False),
    (0x18010A8C, 16, "active FatFs prefix: type drive and cluster size", False),
    (0x18010AA8, 4, "active FatFs cached free-cluster count", False),
    (0x18010AC0, 4, "active FatFs FAT entry count", False),
)
DISK_LIST = ((0x1800C3D4, 8, "disk registry list head next and previous pointers", False),)
DISK_NODE = (
    (0x1800195C, 16, "sole registered disk node identity fields", False),
    (0x1800196C, 16, "sole registered disk geometry and ops pointer", False),
)
DISK_OPS = (
    (0x1800197C, 16, "SD disk operations init/status/read/write pointers", False),
    (0x1800198C, 4, "SD disk operations ioctl pointer", False),
)
DISK_DRIVER_ENTRY = ((0x10025950, 16, "registered SD status callback entry", True),)
DISK_DRIVER_LITERAL = ((0x10025960, 4, "SD status callback global-device pointer literal", False),)
DISK_DRIVER_GLOBAL = ((0x1800C3F0, 4, "SD status callback referenced device pointer", False),)
DISK_DEVICE = (
    (0x100BA160, 16, "SD backend device candidate name/config/API/state fields", False),
    (0x100BA170, 4, "SD backend device candidate data field", False),
)
DISK_DEVICE_REFS = (
    (0x100CAEF3, 3, "SD backend device name prefix", False),
    (0x100BC398, 8, "SD backend config candidate", False),
    (0x18005BE8, 4, "SD backend data first word: controller candidate", False),
    (0x100BC3A0, 16, "SD backend API first four function pointers", False),
)
DISK_CONTROLLER = (
    (0x100CAEE9, 10, "SD config referenced controller-name prefix", False),
    (0x100BA100, 16, "SD data referenced controller device prefix", False),
    (0x100BA110, 4, "controller device data candidate", False),
)
DISK_PHASES = (
    DISK_ENTRY,
    DISK_MORE,
    DISK_VOLUME_BODY,
    DISK_STATUS_ENTRY,
    DISK_STATUS_MORE,
    DISK_REGISTRY_ENTRY,
    DISK_TABLES,
    DISK_REGISTRY_BODY,
    DISK_FS,
    DISK_LIST,
    DISK_NODE,
    DISK_OPS,
    DISK_DRIVER_ENTRY,
    DISK_DRIVER_LITERAL,
    DISK_DRIVER_GLOBAL,
    DISK_DEVICE,
    DISK_DEVICE_REFS,
    DISK_CONTROLLER,
)
DISK_BLOCKS = tuple(block for phase in DISK_PHASES for block in phase)
