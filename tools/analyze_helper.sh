#!/usr/bin/env bash
set -euo pipefail

[[ $# == 2 ]] || { echo 'Usage: analyze_helper.sh PINNED_ADFUS_BIN NEW_OUTPUT_DIRECTORY' >&2; exit 1; }
[[ "$(uname -sm)" == "Linux x86_64" ]] || { echo 'Requires Linux x86_64' >&2; exit 1; }
helper_path="$(realpath "$1")"
output_dir="$(realpath -m "$2")"
tool_dir="${RCOMINOTE_RE_TOOLS:-$HOME/.cache/rcominote/re-tools}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
printf '470827c527a7111cebeb74e60dd32c007390df34453bce519998963db3ad5953  %s\n' "$helper_path" | sha256sum --check
[[ ! -e "$output_dir" ]] || { echo "Refusing existing output: $output_dir" >&2; exit 1; }
test -x "$tool_dir/ghidra_12.1.4_PUBLIC/support/analyzeHeadless"
test -x "$tool_dir/jdk-21.0.12.1+1/bin/java"
mkdir -p "$output_dir/project"

JAVA_HOME="$tool_dir/jdk-21.0.12.1+1" \
    "$tool_dir/ghidra_12.1.4_PUBLIC/support/analyzeHeadless" \
    "$output_dir/project" helper -import "$helper_path" \
    -processor ARM:LE:32:Cortex -cspec default -loader BinaryLoader \
    -loader-baseAddr 0x2ff70000 -scriptPath "$script_dir" \
    -preScript SeedHelper.java -postScript DecompileHelper.java "$output_dir/decompiled.c" \
    -analysisTimeoutPerFile 120 -max-cpu 4 -log "$output_dir/analysis.log"
test -s "$output_dir/decompiled.c"
printf 'Static decompilation saved: %s\n' "$output_dir/decompiled.c"
