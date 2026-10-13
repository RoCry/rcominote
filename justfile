# List named verbs; success changes no files or devices.
[private]
default:
    @just --list

# Green means formatting, lint, shell syntax, and offline tests pass.
[group('dev')]
check:
    bash tools/check.sh

# Offline fixed Android diagnostic APK; no installation or device access.
[group('dev')]
build-android-probe out:
    bash tools/build_android_probe.sh "{{ out }}"

# Linux compiler only; creates an offline fixture, never contacts a device.
[group('firmware')]
build-minimal toolchain out:
    uv run tools/build_minimal_firmware.py "{{ toolchain }}" "{{ out }}"

# Run the recovered local checker in an offline CPU model; rejection exits1.
[group('firmware')]
check-image image:
    uv run tools/check_recovery_image.py docs/evidence/recovery-complete-2026-10-13/recovery-decoded.bin "{{ image }}"

# Partial reference definitions only; compile layout assertions without linking/running.
[group('firmware')]
check-lark toolchain:
    "{{ toolchain }}/bin/arm-none-eabi-gcc" -mcpu=cortex-m4 -mthumb -mfloat-abi=soft -ffreestanding -std=c11 -Wall -Wextra -Werror -pedantic -fsyntax-only firmware/reference/lark_layout_assertions.c
