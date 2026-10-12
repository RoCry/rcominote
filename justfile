default:
    @just --list

setup:
    uv sync --all-extras

test:
    uv run --locked pytest -q

check:
    uv run --locked ruff format --check src tests tools
    uv run --locked ruff check src tests tools
    bash -n tools/setup_sdk.sh
    just test

build:
    uv build

# Unified uv CLI; use --help for all device and offline commands.
comi *args:
    uv run --locked comi {{args}}

scan:
    uv run --locked comi scan

gatt *args:
    uv run --locked comi gatt {{args}}

usb *args:
    uv run --locked comi usb {{args}}

diag *args:
    uv run --locked comi diag {{args}}

code-sample *args:
    uv run --locked comi diag compare-code {{args}}

# Reference board only; never package, download or flash the CoMi.
sdk-setup:
    bash tools/setup_sdk.sh

sdk-build *args:
    uv run --locked tools/build_sdk.py --sdk "$HOME/w/_tmp/lv_port_actions_technology" --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" {{args}}
