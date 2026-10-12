#!/usr/bin/env bash
set -euo pipefail

[[ "$(uname -sm)" == "Linux x86_64" ]] || { echo 'Requires Linux x86_64' >&2; exit 1; }
tool_dir="${RCOMINOTE_RE_TOOLS:-$HOME/.cache/rcominote/re-tools}"
mkdir -p "$tool_dir"
cd "$tool_dir"

fetch() {
    local name="$1" digest="$2" url="$3"
    if [[ ! -f "$name" ]]; then
        curl --fail --location --retry 2 --connect-timeout 15 --max-time 600 --output "$name.part" "$url"
        printf '%s  %s\n' "$digest" "$name.part" | sha256sum --check --status
        mv "$name.part" "$name"
    fi
    printf '%s  %s\n' "$digest" "$name" | sha256sum --check
}

fetch ghidra.zip ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db \
    https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip
fetch jdk21.tar.gz ce79869e1307ed8ee1e2baa86a412b1eb5b75d10a01006d788a6f968bcfaee94 \
    https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_linux_hotspot_21.0.12.1_1.tar.gz

[[ -d ghidra_12.1.4_PUBLIC ]] || unzip -q ghidra.zip
[[ -d jdk-21.0.12.1+1 ]] || tar -xzf jdk21.tar.gz
test -x ghidra_12.1.4_PUBLIC/support/analyzeHeadless
./jdk-21.0.12.1+1/bin/java -version
printf 'Tools ready in %s; system Java unchanged.\n' "$tool_dir"
