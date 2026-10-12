"""Fixed references from the observed SPI Flash RAM read wrapper."""

NOR_TABLE = (
    (0x100BC294, 16, "SPI NOR operation table prefix referenced by RAM wrapper", False),
    (0x100BC2A4, 8, "SPI NOR operation table through actual read slot +14", False),
)
NOR_READ_ENTRY = (
    (0x18000D10, 16, "NOR read table slot target in mapped RAM; never invoked", True),
    (0x18000D20, 16, "NOR read target continuation", True),
)
NOR_READ_BODY = tuple(
    (address, min(16, 0x18000D5C - address), "NOR read boundary branch and mode-helper call code", True)
    for address in range(0x18000D30, 0x18000D60, 16)
)
NOR_MODE_ENTRY = (
    (0x18000C48, 16, "NOR address-mode direct callee; code only", True),
    (0x18000C58, 16, "NOR address-mode cache check continuation", True),
)
NOR_ID_STATE = (
    (0x18000C68, 4, "NOR mode helper chip-ID comparison literal", False),
    (0x18001A9C, 8, "NOR data +20 cached chip ID and +24 flags", False),
    (0x18000C2E, 16, "NOR special-ID mode-exit branch target; code only", True),
    (0x18000C3E, 10, "NOR special-ID branch before known mode helper", True),
)
NOR_PHASES = (NOR_TABLE, NOR_READ_ENTRY, NOR_READ_BODY, NOR_MODE_ENTRY, NOR_ID_STATE)
NOR_BLOCKS = tuple(block for phase in NOR_PHASES for block in phase)
NOR_GUARDS = (
    (
        NOR_ID_STATE,
        (
            (0x100BA004, "58c20b10a41a0018702e00187c1a0018", "NOR device data base"),
            (0x18000C48, "426a19b142f002024262704722f00202", "NOR mode flag load"),
            (0x18000C58, "034b4262026a9a4200d1e4e7704700bf", "NOR cached chip-ID load and comparison"),
        ),
    ),
    (
        NOR_MODE_ENTRY,
        (
            (0x18000D30, "fff78aff2946334642462046fff7dcff", "NOR mode-on and read calls"),
            (0x18000D40, "b9f1807f054603d900212046fff77cff", "NOR mode-off call"),
        ),
    ),
    (
        NOR_READ_BODY,
        (
            (0x18000D10, "2de9f8431e4604460d46904600f0b8fa", "NOR read entry and lock call"),
            (0x18000D20, "06eb0109b9f1807f074603d901212046", "NOR read 16 MiB boundary"),
        ),
    ),
    (
        NOR_READ_ENTRY,
        ((0x100BC2A4, "b70b0018110d0018", "NOR read table target"),),
    ),
    (
        NOR_TABLE,
        (
            (0x180000AC, "94c20b10", "NOR operation table literal"),
            (0x1800007C, "1c4600200cb9bde8f087b4f5004fd9f8", "NOR operation load prefix"),
            (0x1800008C, "143034bfa2464ff4004a1f4632462946", "NOR read slot +14 load suffix"),
        ),
    ),
)
