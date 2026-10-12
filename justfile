# List research commands; the repository has no firmware flash target yet.
default:
    @just --list

# Offline captured-frame protocol tests.
test:
    uv run tools/test_comi.py
    uv run tools/test_usb_inventory.py

# Python style and offline protocol checks, with no device connection.
check:
    ruff format --check tools
    ruff check tools
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
