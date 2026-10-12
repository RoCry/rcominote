#!/usr/bin/env bash
# Fetch the fixed public SDK + GNU Arm toolchain into user-owned directories.
set -euo pipefail

if [[ "$(uname -s):$(uname -m)" != Linux:x86_64 ]]; then
  echo 'SDK setup requires Linux x86_64' >&2
  exit 1
fi
task_source="${1:-$HOME/w/_tmp/lv_port_actions_technology}"
task_cache="${2:-$HOME/.cache/rcominote}"
task_commit=26f51e584940d5b141cd1d09d2629d69b595f579
task_archive=gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2
task_digest=97dbb4f019ad1650b732faffcc881689cedc14e2b7ee863d390e0a41ef16c9a3
task_compiler="$task_cache/gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-gcc"

for task_command in git curl tar bzip2 sha256sum uv cmake ninja; do
  command -v "$task_command" >/dev/null || { echo "Missing command: $task_command" >&2; exit 1; }
done
mkdir -p "$task_cache" "$(dirname "$task_source")"
if [[ ! -e "$task_source" ]]; then
  git clone --no-checkout https://github.com/lvgl/lv_port_actions_technology.git "$task_source"
  git -C "$task_source" checkout --detach "$task_commit"
fi
if [[ "$(git -C "$task_source" rev-parse HEAD)" != "$task_commit" ]] ||
   [[ -n "$(git -C "$task_source" status --porcelain --untracked-files=no)" ]]; then
  echo "SDK checkout must be clean at $task_commit; existing checkout left untouched" >&2
  exit 1
fi
task_temp="$(mktemp -d "$task_cache/setup.XXXXXX")"
trap 'rm -rf -- "$task_temp"' EXIT
if [[ ! -f "$task_cache/$task_archive" ]]; then
  curl --fail --location --silent --show-error --retry 2 --max-time 300 \
    --output "$task_temp/$task_archive" \
    "https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/$task_archive"
  printf '%s  %s\n' "$task_digest" "$task_temp/$task_archive" | sha256sum --check
  mv "$task_temp/$task_archive" "$task_cache/$task_archive"
fi
printf '%s  %s\n' "$task_digest" "$task_cache/$task_archive" | sha256sum --check
if [[ ! -d "${task_compiler%/bin/arm-none-eabi-gcc}" ]]; then
  tar -xjf "$task_cache/$task_archive" -C "$task_temp"
  mv "$task_temp/gcc-arm-none-eabi-10.3-2021.10" "$task_cache/"
fi
"$task_compiler" --version | head -1
echo "SDK: $task_source"
echo "Toolchain: ${task_compiler%/bin/arm-none-eabi-gcc}"
