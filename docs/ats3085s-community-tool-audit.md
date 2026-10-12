# ATS3085S community tools: bounded reuse

2026-10-12. Offline source/container audit; no tool execution against hardware.

## Sources and decision

Pinned [purrrock/ATS3085S_firmware_packer](https://github.com/purrrock/ATS3085S_firmware_packer/tree/e9c3fda2ade79fcd06b1cdbb367ab20bcd289609),
MIT, inspected local clone. Targets DT NO.1/Glyphix watches, not CoMi.
Useful container reference; **do not adopt its BLE flasher or board settings**.
README and How-to explicitly mark direct PC flashing as not working despite
illustrative success output elsewhere. No backup implementation established.

The separately discovered [ATS3085-308X-SDK](https://github.com/AiBTSOcDSP/ATS3085-308X-SDK)
cloned as an empty repository (no HEAD/files). Its name supplies no BSP evidence.
Do not count this as acquisition of matching ATS3085L source.

## Concrete flasher conflicts

`BT_ota_flasher.py` at pinned revision, compared with
[complete CoMi receive dispatcher](ota-wire-contract.md):

| Source behavior | Why unsuitable for CoMi |
|---|---|
| Hard-coded e49a… data/notify and 26078… control UUIDs, watch pre-handshake | Actual CoMi OTA uses F5F0/F5F1/F5F2; no matching watch control protocol established |
| Sends whole image sequentially; never parses opcode03 offset/length | CoMi pulls exact image ranges; unsolicited bytes are not a valid responder |
| Resets PSN every fixed1024 bytes | CoMi resets PSN for each requested range; request size need not be1024 |
| Any other09 notification releases semaphore | Read request/status is not a data ACK; status/body unchecked |
| Any01/02/09 sets same initialization event | Does not correlate expected opcode or validate success code |
| Sends06 and prints firmware-written success | CoMi has no inbound06 handler; device06 is validity reporting, not host reboot |

Therefore changing UUIDs alone cannot repair compatibility. A future updater
must implement actual range requests, negotiated limits, correlated status and
recovery semantics. Do not run this script on CoMi.

Unpacker also writes CRC-mismatched payloads, accepts short directory reads,
joins unvalidated filenames to output paths and continues after decompression
errors. Use its layout as a reference, not as a trusted artifact verifier.

## Independently acquired vendor-hosted sample

URL linked in pinned How-to:
[watch OTA](https://assets2.dt1pro.cn/fw/26/03/02/1772439053925.bin).
Downloaded successfully; attribution comes from the community guide/vendor host,
not a CoMi release record. Binary remains ignored under artifacts/.
[Machine-readable inspection](evidence/ats3085s-reference-ota-2026-10-12.json).

- Outer4274688 bytes; SHA256
  `9ac64acfefad80011ece9b85ad1e986c466b6aab1e074ac6ad9055c26e317328`.
- Existing `uv run comi inspect-ota artifacts/ats3085s-reference-ota.bin`
  validates header/body/all four file CRCs without changing implementation.
- Board `A5S10GLY`, version `1.00_2602281703`; outer entries ota.xml,
  TEMP.bin, sdfs_a.bin, sdfs_k.bin. CoMi board is
  `ats3085l_dvb_watch_ext_nor_max`: **not a matching official image**.
- TEMP starts ACTHHTCA; first `LZMA\x10\0\0\0` at0x11400.
  Each16-byte wrapper is `<4sIII`: magic, header size, compressed size,
  uncompressed size. Two XZ streams:1251940→2097152 and465672→1037824 bytes.
  Python LZMADecompressor independently checked exact output length, EOF and
  no unused compressed input; concatenated output3134976 bytes.
- Inner AOTA passes same existing inspector, contains ota.xml, app.bin3072128,
  sdfs.bin59968. Full inner metadata/hash and chunk offsets retained in JSON.
- This validates our container inspector against an external shipped image,
  beyond its synthetic SDK fixture. It does **not** validate CoMi programming,
  TEMP execution, secure boot or recovery. ACTH boot checksum not checked here.
- Empty `application_gates.known_rejections` checks only three manifest gates;
  does not include board compatibility. This sample demonstrates that limit.

## Next action

Keep format evidence. Continue looking for ATS3085L BSP or exact CoMi package;
never substitute this S-watch payload or its boot stub. Watch-specific flash
instructions add no proven backup/restore route for CoMi.
