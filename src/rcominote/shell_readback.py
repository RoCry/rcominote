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
SHELL_PARSE_HEAD = tuple(
    (address, 16, "shell internal execution argument setup continuation", True)
    for address in range(0x10023060, 0x100230A0, 16)
)
SHELL_PARSE_LOOP = (
    *(
        (address, 16, "shell parser loop condition branch target", True)
        for address in range(0x100231EC, 0x1002320C, 16)
    ),
    *(
        (address, 16, "shell argument tokenizer continuation", True)
        for address in range(0x100230A0, 0x100230E0, 16)
    ),
)
SHELL_LOOKUP_PATH = tuple(
    (address, 16, "shell zero-level command lookup branch target", True)
    for address in range(0x10023128, 0x10023168, 16)
)
SHELL_FIND_COMMAND = tuple(
    (address, 16, "shell three-argument command lookup callee", True)
    for address in range(0x100A0F94, 0x100A0FD4, 16)
)
SHELL_REGISTRY_ENTRY = (
    (0x100A0FD4, 16, "command lookup comparison-loop continuation", True),
    *(
        (address, 16, "command registry direct callee root branch", True)
        for address in range(0x10023D50, 0x10023D90, 16)
    ),
)
SHELL_REGISTRY_BOUNDS = (
    (0x10023D90, 4, "static subcommand lookup return branch", True),
    (0x10023D94, 8, "root registry start and end literals", False),
    (0x100A0FE4, 6, "command lookup epilogue continuation", True),
)
SHELL_ROOT_TABLE = tuple(
    (address, min(16, 0x100BA6DC - address), "bounded 13-entry root command registry", False)
    for address in range(0x100BA674, 0x100BA6DC, 16)
)
SHELL_ROOT_DESCRIPTORS = (
    (0x100BCE4C, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BA878, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BD83C, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB6C4, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BBFC4, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB8C0, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB630, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB674, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB6D8, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB59C, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB6EC, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BB700, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
    (0x100BCD08, 16, "root registry descriptor syntax/help/subcmd/handler prefix", False),
)
SHELL_ROOT_NAMES = (
    (0x100D1763, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100D454E, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100D5F63, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C5FBC, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C9420, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C69DD, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C5A99, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C5E43, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C5F7D, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C591F, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C5ED1, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100D1795, 4, "root command syntax prefix; only NUL proves complete name", False),
    (0x100C0F23, 4, "root command syntax prefix; only NUL proves complete name", False),
)
SHELL_DBG_SUBCOMMAND = (
    (0x100BBBA4, 8, "confirmed dbg subcommand descriptor dynamic flag and pointer", False),
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
    SHELL_PARSE_HEAD,
    SHELL_PARSE_LOOP,
    SHELL_LOOKUP_PATH,
    SHELL_FIND_COMMAND,
    SHELL_REGISTRY_ENTRY,
    SHELL_REGISTRY_BOUNDS,
    SHELL_ROOT_TABLE,
    SHELL_ROOT_DESCRIPTORS,
    SHELL_ROOT_NAMES,
    SHELL_DBG_SUBCOMMAND,
)
SHELL_BLOCKS = tuple(block for phase in SHELL_PHASES for block in phase)
SHELL_GUARDS = (
    (
        SHELL_DBG_SUBCOMMAND,
        (
            (0x100BB8C0, "dd690c10e1690c10a4bb0b1000000000", "dbg syntax and subcommand descriptor"),
            (0x100C69DD, "64626700", "confirmed dbg name"),
        ),
    ),
    (
        SHELL_ROOT_NAMES,
        (
            (0x100BCE4C, "63170d101e170d1000cf0b1000000000", "root descriptor syntax pointer"),
            (0x100BA878, "4e450d1067090c108ca80b1001210010", "root descriptor syntax pointer"),
            (0x100BD83C, "635f0d10875d0d1050d80b10fdcd0610", "root descriptor syntax pointer"),
            (0x100BB6C4, "bc5f0c10c25f0c10000000001d450210", "root descriptor syntax pointer"),
            (0x100BBFC4, "20940c10aa930c108cc00b1000000000", "root descriptor syntax pointer"),
            (0x100BB8C0, "dd690c10e1690c10a4bb0b1000000000", "root descriptor syntax pointer"),
            (0x100BB630, "995a0c10a05a0c106cb60b10fd2b0210", "root descriptor syntax pointer"),
            (0x100BB674, "435e0c10e55d0c1000000000653b0210", "root descriptor syntax pointer"),
            (0x100BB6D8, "7d5f0c10855f0c100000000081450210", "root descriptor syntax pointer"),
            (0x100BB59C, "1f590c1026590c1028b60b1000000000", "root descriptor syntax pointer"),
            (0x100BB6EC, "d15e0c10d85e0c102cb70b101d460210", "root descriptor syntax pointer"),
            (0x100BB700, "95170d10965f0c1034b70b1000000000", "root descriptor syntax pointer"),
            (0x100BCD08, "230f0c10e40d0d1094cd0b1000000000", "root descriptor syntax pointer"),
        ),
    ),
    (
        SHELL_ROOT_DESCRIPTORS,
        (
            (0x100BA674, "000000004cce0b100000000078a80b10", "root registry descriptor pointers"),
            (0x100BA684, "000000003cd80b1000000000c4b60b10", "root registry descriptor pointers"),
            (0x100BA694, "00000000c4bf0b1000000000c0b80b10", "root registry descriptor pointers"),
            (0x100BA6A4, "0000000030b60b100000000074b60b10", "root registry descriptor pointers"),
            (0x100BA6B4, "00000000d8b60b10000000009cb50b10", "root registry descriptor pointers"),
            (0x100BA6C4, "00000000ecb60b100000000000b70b10", "root registry descriptor pointers"),
            (0x100BA6D4, "0000000008cd0b10", "root registry descriptor pointers"),
        ),
    ),
    (SHELL_ROOT_TABLE, ((0x10023D94, "74a60b10dca60b10", "shell root registry start/end"),)),
    (
        SHELL_REGISTRY_BOUNDS,
        (
            (0x10023D50, "10b50b46144650b90e490f4a521ab3eb", "shell root registry bound literals"),
            (0x10023D80, "002bf2d10024f0e714204343d418d358", "shell static descriptor stride"),
            (0x100A0FD4, "28b1296830465ff775fe0028f0d12846", "shell command comparison and epilogue"),
        ),
    ),
    (
        SHELL_REGISTRY_ENTRY,
        ((0x100A0FC4, "41463a46204682f7c1fe08f101080546", "shell indexed registry call"),),
    ),
    (
        SHELL_FIND_COMMAND,
        ((0x10023128, "baf1000f05d1396807aa58467df02eff", "shell three-argument lookup call"),),
    ),
    (
        SHELL_LOOKUP_PATH,
        ((0x100230D0, "059b4bb3386801f00dfa98b166b1a568", "shell zero-level command branch"),),
    ),
    (
        SHELL_PARSE_LOOP,
        (
            (0x10023080, "0532012a00f0d7800b2b40f2af800699", "shell loop condition target"),
            (0x10023090, "022940f0af808b4b8b4a15e00223039a", "shell tokenizer setup continuation"),
        ),
    ),
    (
        SHELL_PARSE_HEAD,
        ((0x10023050, "96f03afb204600f0dbfea168e0688a8f", "shell internal setup continuation"),),
    ),
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
