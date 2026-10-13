# Bounded Android host experiment

Research tool, Android12/API31+, fixed owned card `C261CF0430` /
`50:C0:F0:AE:7C:0E` / FW010004. Not an alternative vendor app or NOR exporter.

- `info`: validate CRC + serial, query idle device info, disconnect.
- `help`: same identity/status gate, Actions PREPARE→START→help→STOP,
  query device info again; full payload must equal initial state.
- One GATT operation at a time; separate Android write callback and protocol ACK.
  Requests HIGH priority + MTU512; records actual MTU, including unsolicited changes.
- Raw callbacks copied before dispatch; monotonic callback and persistence timestamps.
  Internal JSONL refuses overwrite; bounded512KiB/1024rows, total60s.
- First failure sticky; no parser resync. START attempt triggers one independent
  STOP attempt when link permits; raw cleanup window4.5s. Disconnection/wedged
  operation cannot guarantee STOP. Result explicitly distinguishes confirmation.
- Only `BLUETOOTH_CONNECT`; no Internet, scan, account, OTA, arbitrary command,
  recording, storage erase/write, reboot or firmware operation.

## Build

Requires `unzip`, `zip`, `rg`, JDK21 from `tools/setup_re_tools.sh` or
`RCOMINOTE_JDK_HOME`. Official SDK archives in
`~/.cache/rcominote/android-tools/`:

| Archive | Official URL | Repository SHA1 |
|---|---|---|
| platform31 | https://dl.google.com/android/repository/platform-31_r01.zip | `ca5bcaa565cb37e9d287051d6dd0e49a5426ec29` |
| buildtools35 | https://dl.google.com/android/repository/build-tools_r35_linux.zip | `2cfaa0bbb2336e9ec18ed3ecea84fa2e2af607bc` |

Hashes read from [Google SDK repository](https://dl.google.com/android/repository/repository2-1.xml),
2026-10-13; build script verifies before content-addressed extraction. Cache key
is local debug identity; generated once, never committed. Build output must be new:

```sh
just build-android-probe artifacts/android-probe-NEW
```

## Controlled run

Disconnect other hosts/vendor app first. Authorize ADB normally. MIUI may require
USB installation setting or normal on-device APK installation. Full HCI logging
requires Developer options→Bluetooth HCI snoop log→Enabled, then Bluetooth restart;
verify `dumpsys bluetooth_manager` shows `mSnoopLogSettingAtEnable = full`.

```sh
adb -s PHONE install artifacts/android-probe-NEW/comi-probe.apk
adb -s PHONE shell pm grant site.rocry.rcominote.probe android.permission.BLUETOOTH_CONNECT
adb -s PHONE shell am start -n site.rocry.rcominote.probe/.MainActivity \
  --es mode info --es run info-NEW
# Wait for persisted result; do not interrupt an active session with am force-stop.
adb -s PHONE exec-out run-as site.rocry.rcominote.probe cat files/info-NEW.jsonl > artifacts/info-NEW.jsonl
uv run tools/verify_android_probe.py artifacts/info-NEW.jsonl
```

After baseline succeeds, launch once with `--activity-clear-top`, `mode help`
and a distinct run name; replace an Activity only after its result is persisted.
Offline verifier independently parses raw
notifications, requires4ACK/F1/no residue, and compares three F0 frames to
`docs/evidence/log-commands-2026-10-12.json`. It fails even if APK labels a damaged
stream successful. It never repairs bytes; changed text alone does not establish loss.

Collect `adb bugreport artifacts/bugreport-NEW.zip` after experiment; inspect all
snoop members, including `.last`, separately. The compressed BTSNOOP_LOG_SUMMARY
fallback may contain no ACL payload; file presence is not capture acceptance.
Use existing `btmon -r SNOOP` to decode. Match target connection, discovered handles,
negotiated parameters and callback bytes before attributing loss. HCI remains a host
boundary, not an over-the-air/device-send trace.

2026-10-13 capture reproducibility:

```sh
uv run tools/verify_android_log_capture.py artifacts/android-20261013
```

This second verifier pins the actual H4 capture SHA, validates complete snoop
records, binds handle5 to the observed owned public address, resolves
characteristic handles from same-connection discovery and compares all
notifications/writes with raw Android callbacks. It accepts only this observed
unfragmented CID4 trace; unsupported layout fails instead of guessing reassembly.
