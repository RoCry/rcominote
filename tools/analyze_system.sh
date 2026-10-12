#!/usr/bin/env bash
set -euo pipefail

[[ $# == 2 ]] || { echo 'Usage: analyze_system.sh VERIFIED_MAPPED_SYSTEM_BIN NEW_OUTPUT_DIRECTORY' >&2; exit 1; }
[[ "$(uname -sm)" == "Linux x86_64" ]] || { echo 'Requires Linux x86_64' >&2; exit 1; }
image_path="$(realpath "$1")"
output_dir="$(realpath -m "$2")"
tool_dir="${RCOMINOTE_RE_TOOLS:-$HOME/.cache/rcominote/re-tools}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ ! -e "$output_dir" ]] || { echo "Refusing existing output: $output_dir" >&2; exit 1; }
uv run --directory "$script_dir/.." comi image inspect "$image_path"
test -x "$tool_dir/ghidra_12.1.4_PUBLIC/support/analyzeHeadless"
test -x "$tool_dir/jdk-21.0.12.1+1/bin/java"
mkdir -p "$output_dir/project"

JAVA_HOME="$tool_dir/jdk-21.0.12.1+1" \
    "$tool_dir/ghidra_12.1.4_PUBLIC/support/analyzeHeadless" \
    "$output_dir/project" system -import "$image_path" \
    -processor ARM:LE:32:Cortex -cspec default -loader BinaryLoader \
    -loader-baseAddr 0x10000000 -scriptPath "$script_dir" \
    -preScript SystemImage.java seed -postScript SystemImage.java export "$output_dir/decompiled.c" \
    -analysisTimeoutPerFile 300 -max-cpu 4 -log "$output_dir/analysis.log"
test -s "$output_dir/decompiled.c"
printf 'Static mapped-system decompilation saved: %s\n' "$output_dir/decompiled.c"
