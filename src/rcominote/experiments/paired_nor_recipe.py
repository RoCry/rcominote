"""Exact immutable NOR recipe, Actions receipt and retained-ring policy dispatch."""

from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import scratch_system_pair_contract as legacy
from rcominote.experiments.sd_bridge import console_packet
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE

PAGE_PROFILE = "immutable-physical-nor-pair-page-v2"
PAGE_PROFILE_V3 = "immutable-physical-nor-pair-page-v3"
PAGE_PROFILE_V4 = "immutable-physical-nor-pair-page-v4"
PAGE_PROFILE_V5 = "immutable-physical-nor-pair-page-v5"
ACTIONS_POLICY = legacy.ACTIONS_POLICY


def recipe(op):
    offset, nonce = op.get("nor_offset"), op.get("nonce")
    if type(offset) is not int or offset % 512 or not 0 <= offset <= 0x400000 - 512:
        raise ValueError("Requires aligned512 physical NOR target within4MiB")
    if "prefix_policy" in op and op["prefix_policy"] not in (
        F.PADDING_POLICY,
        F.STATUS_POLICY,
        F.FORMAT_POLICY,
    ):
        raise ValueError("Unknown producer prefix policy")
    if (
        not isinstance(nonce, str)
        or F.NONCE.fullmatch(nonce) is None
        or op.get("operation_id") not in ("first", "second")
        or op.get("name") != F.NAME
        or op.get("uptime_command") != f"kernel uptime {nonce}"
        or op.get("producer") != f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}"
        or op.get("dump_command") != F.DUMP
    ):
        raise ValueError("Producer differs from immutable physical NOR/same-file/nonce recipe")
    return [
        PREPARE,
        START,
        *(console_packet(op[k]) for k in ("uptime_command", "producer", "dump_command")),
        STOP,
    ]


def actions(report, op):
    return legacy.A.action_frames(report, op, expected=recipe(op)) | {
        "f0_frames": sum(frame["command"] == 0xF0 for frame in op["frames"]),
        "uptime_body_required": False,
        "policy": ACTIONS_POLICY,
    }


def payload(op, current, previous):
    recipe(op)
    policy = op.get("prefix_policy", F.STRICT_POLICY)
    sector, proof = F._parse_ring(
        current, previous, nonce=op["nonce"], nor_offset=op["nor_offset"], prefix_policy=policy
    )
    return {
        "freshness": proof
        | {
            "target_profile": {
                F.STRICT_POLICY: PAGE_PROFILE,
                F.PADDING_POLICY: PAGE_PROFILE_V3,
                F.STATUS_POLICY: PAGE_PROFILE_V4,
                F.FORMAT_POLICY: PAGE_PROFILE_V5,
            }[policy]
        },
        "sector_hex": sector.hex(),
        "independent_oracle": False,
    }
