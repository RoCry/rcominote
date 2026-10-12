# List research commands; the repository has no firmware flash target yet.
default:
    @just --list

# Offline captured-frame protocol tests.
test:
    uv run tools/test_comi.py
    uv run tools/test_usb_inventory.py
    uv run tools/test_log_capture.py

# Python style and offline protocol checks, with no device connection.
check:
    ruff format --check tools
    ruff check tools
    bash -n tools/setup_sdk.sh
    just test

# Discover CoMi advertisements; no connection.
scan:
    uv run tools/comi.py scan

# Snapshot GATT services without application writes; select the owned serial.
gatt *args:
    uv run tools/gatt.py {{args}}

# BLE CLI; state-changing operations must be selected explicitly.
comi *args:
    uv run tools/comi.py {{args}}

# Read the macOS USB registry or compare captures; no device commands.
usb *args:
    uv run tools/usb_inventory.py {{args}}

# Send one fixed log PREPARE handshake; no shell, dump, or reset.
log-probe *args:
    uv run tools/log_probe.py {{args}}

# Linux x86_64: fetch the pinned public SDK and checksum-verified GNU Arm compiler.
sdk-setup:
    bash tools/setup_sdk.sh

# Compile reference-board hello_world; never package, download, or flash.
sdk-build *args:
    uv run --locked tools/build_sdk.py --sdk "$HOME/w/_tmp/lv_port_actions_technology" --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" {{args}}

# Bounded log session and explicit fixed diagnostic queries.
log-capture *args:
    uv run tools/log_capture.py {{args}}
