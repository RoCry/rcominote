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
SHELL_PHASES = (
    SHELL_INIT_SUCCESS,
    SHELL_STREAM_SUCCESS,
    SHELL_TIMER_REFS,
    SHELL_TIMER_CODE,
    SHELL_SERVICE_HEAD,
    SHELL_SERVICE_SUCCESS,
)
SHELL_BLOCKS = tuple(block for phase in SHELL_PHASES for block in phase)
SHELL_GUARDS = (
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
