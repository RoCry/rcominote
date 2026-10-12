"""Fixed device-registry references toward identifying boot storage."""

BOOT_BINDING = (
    (0x1009A81C, 16, "device binding direct callee entry; never invoked", True),
    (0x1009A82C, 16, "device binding code continuation", True),
)
BOOT_BINDING_BODY = (
    (0x1009A83C, 16, "device binding string fallback and pointer loop", True),
    (0x1009A84C, 16, "device binding ready/name comparison", True),
    (0x1009A85C, 16, "device binding string loop continuation", True),
    (0x1009A86C, 8, "device binding return before literal pool", True),
    (0x1009A874, 12, "device binding referenced bounds and message literals", False),
)
BOOT_DEVICE_NAMES = tuple(
    (address, 4, "device table name pointer within actual start/end and 32-byte stride", False)
    for address in range(0x100B9F40, 0x100BA320, 32)
    if address not in (0x100BA100, 0x100BA160)
)
BOOT_NAME_POINTERS = (
    (0x100B9F40, 0x100C98B9),
    (0x100B9F60, 0x100C0E7F),
    (0x100B9F80, 0x100C9B81),
    (0x100B9FA0, 0x100C9B85),
    (0x100B9FC0, 0x100C9029),
    (0x100B9FE0, 0x100C7A95),
    (0x100BA000, 0x100C10E9),
    (0x100BA020, 0x100C7E39),
    (0x100BA040, 0x100C7E50),
    (0x100BA060, 0x100C50F5),
    (0x100BA080, 0x100C9FB2),
    (0x100BA0A0, 0x100C3784),
    (0x100BA0C0, 0x100C7CDD),
    (0x100BA0E0, 0x100C7B05),
    (0x100BA120, 0x100C50F8),
    (0x100BA140, 0x100CC3A8),
    (0x100BA180, 0x100CAADF),
    (0x100BA1A0, 0x100C8119),
    (0x100BA1C0, 0x100C7CD5),
    (0x100BA1E0, 0x100CA42A),
    (0x100BA200, 0x100C803B),
    (0x100BA220, 0x100C85A9),
    (0x100BA240, 0x100CDAF3),
    (0x100BA260, 0x100CDC02),
    (0x100BA280, 0x100C19F6),
    (0x100BA2A0, 0x100C5138),
    (0x100BA2C0, 0x100C8946),
    (0x100BA2E0, 0x100C9E3F),
    (0x100BA300, 0x100C26D7),
)
BOOT_NAME_TEXT = tuple(
    (name, 16, "device name string prefix; stop interpretation at NUL", False)
    for _, name in BOOT_NAME_POINTERS
)
BOOT_FLASH_DEVICES = (
    (0x100BA004, 16, "spi_flash config/API/state/data pointers", False),
    (0x100BA084, 16, "sim_flash config/API/state/data pointers", False),
    (0x100B890A, 16, "device-ready direct callee entry; never invoked", True),
)
BOOT_FLASH_REFS = (
    (0x100BC258, 16, "spi_flash configuration prefix", False),
    (0x18001AA4, 16, "spi_flash API prefix; pointers only", False),
    (0x18001AB4, 8, "spi_flash API parameter/layout callback candidates", False),
    (0x18001A7C, 16, "spi_flash data prefix; no MMIO dereference", False),
    (0x18002E70, 2, "spi_flash device state halfword used by ready helper", False),
    (0x100BC268, 16, "sim_flash API prefix; pointers only", False),
    (0x100B891A, 4, "device-ready return continuation", True),
)
BOOT_FLASH_CODE = (
    (0x1800006C, 16, "spi_flash read callback in mapped RAM; never invoked", True),
    (0x1800007C, 16, "spi_flash read callback continuation", True),
    (0x100A4A06, 10, "spi_flash page-layout callback", True),
    (0x10031440, 4, "spi_flash parameter callback", True),
    (0x10031444, 4, "spi_flash parameter pointer literal", False),
)
BOOT_FLASH_MORE = (
    (0x1800008C, 16, "spi_flash RAM read loop continuation", True),
    (0x1800009C, 16, "spi_flash RAM read loop and return", True),
    (0x180000AC, 4, "spi_flash RAM read referenced literal", False),
    (0x100BC250, 8, "spi_flash returned parameter structure", False),
)
BOOT_PHASES = (
    BOOT_BINDING,
    BOOT_BINDING_BODY,
    BOOT_DEVICE_NAMES,
    BOOT_NAME_TEXT,
    BOOT_FLASH_DEVICES,
    BOOT_FLASH_REFS,
    BOOT_FLASH_CODE,
    BOOT_FLASH_MORE,
)
BOOT_BLOCKS = tuple(block for phase in BOOT_PHASES for block in phase)
BOOT_GUARDS = (
    (
        BOOT_FLASH_MORE,
        (
            (0x1800006C, "2de9f047dff83890d0f810800d461646", "spi_flash read entry and literal load"),
            (0x1800007C, "1c4600200cb9bde8f087b4f5004fd9f8", "spi_flash read loop"),
            (0x10031444, "50c20b10", "spi_flash parameter literal"),
        ),
    ),
    (
        BOOT_FLASH_CODE,
        (
            (0x18001AA4, "6d000018b1000018c5000018d1000018", "spi_flash RAM read callback pointer"),
            (0x18001AB4, "41140310074a0a10", "spi_flash metadata callback pointers"),
        ),
    ),
    (
        BOOT_FLASH_REFS,
        (
            (0x100BA004, "58c20b10a41a0018702e00187c1a0018", "spi_flash instance pointers"),
            (0x100BA084, "0000000068c20b10d82e001800000000", "sim_flash instance pointers"),
            (0x100B890A, "38b1c3681888c0f30800a0f580735842", "device-ready state halfword load"),
        ),
    ),
    (
        BOOT_FLASH_DEVICES,
        (
            (0x100BA000, "e9100c10", "spi_flash name pointer"),
            (0x100BA080, "b29f0c10", "sim_flash name pointer"),
            (0x1009A83C, "a4fb002414e020461ef061f810b12368", "device readiness direct call"),
        ),
    ),
    *(
        (((name, 16, "", False),), ((parent, name.to_bytes(4, "little").hex(), "device name pointer"),))
        for parent, name in BOOT_NAME_POINTERS
    ),
    (
        BOOT_DEVICE_NAMES,
        (
            (0x1009A874, "20a30b10409f0b103ece0d10", "device table start and end literals"),
            (0x1009A84C, "ab420dd02034ebe720461ef058f808b9", "device table iteration stride"),
        ),
    ),
    (
        BOOT_BINDING_BODY,
        (
            (0x1009A81C, "70b5054630b3047814b3134a134c1646", "device binding entry and literal loads"),
            (0x1009A82C, "944208d1114cb4420ed11148294605f0", "device binding range and fallback"),
        ),
    ),
    (
        BOOT_BINDING,
        (
            (0x10025A54, "1378082be6d02860e4e70192134874f0", "device binding BL prefix"),
            (0x10025A64, "dbfe0028dcd0019a2146ece76ff01500", "device binding BL suffix"),
        ),
    ),
)
