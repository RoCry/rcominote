"""Instruction-derived SD/MMC read phases and their live prerequisites."""

CARD_ENTRY = (
    (0x10025A14, 16, "registered SD disk ioctl code entry; never invoked", True),
    (0x10025A24, 16, "SD disk ioctl continuation", True),
    (0x100A4EF4, 16, "SD flash API read callback code entry; never invoked", True),
    (0x100A4F04, 4, "SD flash API read callback return", True),
)
CARD_CONTROLLER = ((0x100BC3BC, 16, "MMC_1 controller config prefix; no MMIO dereference", False),)
CARD_IO_BODY = (
    *(
        (
            address,
            min(16, 0x10025AAC - address),
            "SD disk ioctl code or absolute jump table",
            address < 0x10025A84,
        )
        for address in range(0x10025A34, 0x10025AAC, 16)
    ),
    (0x10025AAC, 8, "SD ioctl global-device and binding-name literals", False),
    (0x100335E0, 16, "SD read common-transfer callee entry; never invoked", True),
    (0x100335F0, 16, "SD common-transfer continuation", True),
)
CARD_STATE_ENTRY = (
    (0x10033A20, 16, "SD storage ioctl direct callee entry; never invoked", True),
    (0x10033A30, 16, "SD storage ioctl continuation", True),
    *(
        (address, 16, "SD common transfer suspend and readiness path", True)
        for address in range(0x10033600, 0x10033660, 16)
    ),
)
CARD_STATE_MORE = (
    *(
        (address, 16, "SD transfer low-power/type branch", True)
        for address in range(0x10033660, 0x100336A0, 16)
    ),
    (0x10033A40, 4, "SD storage ioctl TBH instruction", True),
    (0x10033A44, 16, "SD storage ioctl halfword branch table prefix", False),
    (0x10033A54, 8, "SD storage ioctl halfword branch table suffix", False),
    (0x10033A5C, 16, "SD storage ioctl cached count and return cases", True),
    (0x10033A6C, 12, "SD storage ioctl cached sector size and fixed erase size", True),
    (0x10033A78, 16, "SD storage ioctl detection branch", True),
)
CARD_STATE_RAM = ((0x18005D58, 16, "SD data +170 type/state/RCA/CSD-prefix cached fields", False),)
CARD_TYPE_BRANCH = (
    (0x100336B2, 16, "SD type-one low-power branch", True),
    (0x100336C2, 16, "SD type-one low-power continuation", True),
    (0x18005D68, 4, "SD cached sector-size field derived from ioctl case", False),
)
CARD_PHASES = (
    CARD_ENTRY,
    CARD_CONTROLLER,
    CARD_IO_BODY,
    CARD_STATE_ENTRY,
    CARD_STATE_MORE,
    CARD_STATE_RAM,
    CARD_TYPE_BRANCH,
)
CARD_BLOCKS = tuple(block for phase in CARD_PHASES for block in phase)
CARD_GUARDS = (
    (
        CARD_TYPE_BRANCH,
        (
            (0x10033660, "012b84f8731124d0d4f87421206804f5", "SD type-one conditional branch"),
            (0x10033A6C, "d5f88031f6e74ff40073f3e7", "SD cached sector-size load"),
        ),
    ),
    (
        CARD_STATE_MORE,
        (
            (0x10033650, "71f044fc94f873316bb194f870310021", "SD low-power/type loads"),
            (0x10033A20, "2de9f341056995f87131144623b90a29", "SD storage ioctl state load"),
            (0x10033A30, "22d06ff0010415e001390b2900f2e580", "SD storage ioctl range check"),
        ),
    ),
    (
        CARD_STATE_RAM,
        (
            (0x100BA170, "e85b0018", "SD driver data base"),
            (0x10033650, "71f044fc94f873316bb194f870310021", "SD state field offsets"),
        ),
    ),
    (
        CARD_STATE_ENTRY,
        (
            (0x10025A34, "f8e7012103b0bde830400df0efbf2146", "SD storage ioctl direct tail call"),
            (0x100335E0, "2de9f04f04692ded028b9b4694f86831", "SD common transfer entry"),
            (0x100335F0, "8bb0824688461546abb104f5ac7104f1", "SD common transfer branch"),
        ),
    ),
    (
        CARD_IO_BODY,
        (
            (0x10025A14, "37b5254d034628680c4650bb0a291cd0", "SD disk ioctl entry"),
            (0x100A4EF4, "07b5009313460a4600218ef76ffb03b0", "SD read direct transfer call"),
        ),
    ),
    (
        CARD_ENTRY,
        (
            (0x1800198C, "155a0210", "SD ioctl callback pointer"),
            (0x100BC3A0, "f54e0a10e14e0a100000000000000000", "SD read callback pointer"),
        ),
    ),
    (CARD_CONTROLLER, ((0x100BA100, "e9ae0c10bcc30b10d4c30b1078300018", "MMC_1 config pointer"),)),
)
