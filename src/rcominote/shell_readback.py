"""Fixed code edges from logsrv toward the shell registry and partition lookup."""

SHELL_INIT_SUCCESS = (
    (0x1000BF58, 16, "logsrv allocation-success branch target; code only", True),
    (0x1000BF68, 16, "logsrv initialization success continuation", True),
)
SHELL_STREAM_SUCCESS = (
    (0x1000BF82, 16, "logsrv stream-create non-null branch target", True),
    (0x1000BF92, 16, "logsrv callback-registration continuation", True),
)
SHELL_TIMER_REFS = (
    (0x1000C0CC, 8, "logsrv callback argument and context global literals", False),
    (0x1009C8CC, 16, "timer-registration direct callee entry; never invoked", True),
    (0x1009C8DC, 16, "timer-registration argument handling", True),
)
SHELL_TIMER_CODE = (
    (0x1009C8EC, 12, "timer-registration callback stores and return", True),
    (0x1000C0E8, 16, "logsrv registered timer callback entry; never invoked", True),
    (0x1000C0F8, 16, "logsrv timer callback continuation", True),
)
SHELL_SERVICE_HEAD = tuple(
    (address, 16, "logsrv callback service-header parsing continuation", True)
    for address in range(0x1000C108, 0x1000C148, 16)
)
SHELL_SERVICE_SUCCESS = tuple(
    (address, 16, "logsrv matched service-ID branch continuation", True)
    for address in range(0x1000C150, 0x1000C190, 16)
)
SHELL_TLV_HEAD = tuple(
    (address, 16, "logsrv service command TLV continuation", True)
    for address in range(0x1000C190, 0x1000C1D0, 16)
)
SHELL_TLV_BODY = tuple(
    (address, 16, "logsrv TLV header-read success target and continuation", True)
    for address in range(0x1000C1F4, 0x1000C234, 16)
)
SHELL_TLV_DISPATCH = tuple(
    (address, 16, "logsrv bounded TLV payload success target and dispatch", True)
    for address in range(0x1000C256, 0x1000C296, 16)
)
SHELL_TEXT = tuple(
    (address, 16, "logsrv TLV type-1 text branch target and continuation", True)
    for address in range(0x1000C2CC, 0x1000C30C, 16)
)
SHELL_EXECUTE_ENTRY = (
    (0x100242A8, 4, "actual backend getter code ending at BX LR", True),
    (0x100242AC, 4, "backend getter literal after return", False),
    (0x100242B0, 16, "actual text-branch callback registration callee", True),
    (0x100A0E1A, 16, "actual text-branch execute candidate entry", True),
    (0x100A0E2A, 16, "execute candidate argument validation continuation", True),
)
SHELL_EXECUTE_BODY = (
    (0x100A0E3A, 16, "execute candidate command-buffer and mutex continuation", True),
    (0x100A0E4A, 16, "execute candidate internal dispatch call", True),
    (0x100A0E5A, 16, "execute candidate cleanup continuation", True),
    (0x100A0E6A, 8, "execute candidate success epilogue", True),
)
SHELL_INTERNAL_EXECUTE = tuple(
    (address, 16, "shell command execution direct callee entry and continuation", True)
    for address in range(0x10023020, 0x10023060, 16)
)
SHELL_PHASES = (
    SHELL_INIT_SUCCESS,
    SHELL_STREAM_SUCCESS,
    SHELL_TIMER_REFS,
    SHELL_TIMER_CODE,
    SHELL_SERVICE_HEAD,
    SHELL_SERVICE_SUCCESS,
    SHELL_TLV_HEAD,
    SHELL_TLV_BODY,
    SHELL_TLV_DISPATCH,
    SHELL_TEXT,
    SHELL_EXECUTE_ENTRY,
    SHELL_EXECUTE_BODY,
    SHELL_INTERNAL_EXECUTE,
)
SHELL_BLOCKS = tuple(block for phase in SHELL_PHASES for block in phase)
SHELL_GUARDS = (
    (
        SHELL_INTERNAL_EXECUTE,
        ((0x100A0E4A, "3d70fff784ff204682f7e5f80546a068", "shell internal execute call"),),
    ),
    (
        SHELL_EXECUTE_BODY,
        ((0x100A0E2A, "11b3ff2823d82cb3a068423018f03cfd", "shell execute validation and copy call"),),
    ),
    (
        SHELL_EXECUTE_ENTRY,
        (
            (0x1000C2DC, "50461346224649f055fe29461f4817f0", "logsrv text callback setup"),
            (0x1000C2EC, "e1ff17f0dbff154994f091fd39463846", "logsrv backend getter and execute calls"),
        ),
    ),
    (SHELL_TEXT, ((0x1000C256, "17b1012f37d0f5e7022c12d1394a3d49", "logsrv type-1 text branch"),)),
    (
        SHELL_TLV_DISPATCH,
        ((0x1000C214, "7bfc18b14c484d493043d8e7402c18d9", "logsrv bounded TLV payload branch"),),
    ),
    (SHELL_TLV_BODY, ((0x1000C1C0, "4046fff7a3fca8b146f0b9705c4940f0", "logsrv TLV header success branch"),)),
    (
        SHELL_TLV_HEAD,
        ((0x1000C180, "6a4b334304936a4b46f0337b334346ea", "logsrv service command continuation"),),
    ),
    (
        SHELL_SERVICE_SUCCESS,
        ((0x1000C138, "9df81c201d2a07d046f03b70764940f0", "logsrv service-ID success branch"),),
    ),
    (
        SHELL_SERVICE_HEAD,
        (
            (0x1009C8EC, "c4e90565c4e9004470bd00bf", "timer callback and context stores"),
            (0x1000C0F8, "45f08efa042810d92868834e052207a9", "logsrv service-header setup"),
        ),
    ),
    (
        SHELL_TIMER_CODE,
        (
            (0x1000C0CC, "e9c00010aca90018", "logsrv callback and context literals"),
            (0x1009C8CC, "70b50e461546044670b1084b01469868", "timer callback argument preservation"),
            (0x1009C8DC, "1cf062fe1422002104f108001cf0eefe", "timer initialization continuation"),
        ),
    ),
    (
        SHELL_TIMER_REFS,
        (
            (0x1000BF82, "04f13c00acf0a6fd5049504fdff85491", "logsrv callback literal load"),
            (0x1000BF92, "224604f1200090f098fc4d484e493c60", "logsrv timer arguments and direct call"),
        ),
    ),
    (
        SHELL_STREAM_SUCCESS,
        ((0x1000BF68, "60f0ecfe206040b95448554930434af0", "logsrv stream success branch"),),
    ),
    (
        SHELL_INIT_SUCCESS,
        ((0x1000BF30, "604bf61a760106f47f46044660b946f0", "logsrv non-null branch target"),),
    ),
)
