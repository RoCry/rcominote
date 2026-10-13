#!/usr/bin/env bash
# Build only: no adb, installation, connection or device commands.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_cache="${XDG_CACHE_HOME:-$HOME/.cache}/rcominote/android-tools"
jdk_root="${RCOMINOTE_JDK_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/rcominote/re-tools/jdk-21.0.12.1+1}"
out_dir="${1:-$repo_root/artifacts/android-probe-build}"
[[ ! -e "$out_dir" ]] || { echo "Refusing existing output directory: $out_dir" >&2; exit 1; }
[[ -x "$jdk_root/bin/javac" ]] || { echo "Missing JDK: $jdk_root" >&2; exit 1; }
verify_archive() {
    local name="$1" expected="$2" actual
    actual="$(sha1sum "$sdk_cache/$name")"
    [[ "${actual%% *}" == "$expected" ]] || { echo "SDK archive SHA1 mismatch: $name" >&2; exit 1; }
}
verify_archive platform-31_r01.zip ca5bcaa565cb37e9d287051d6dd0e49a5426ec29
verify_archive build-tools_r35_linux.zip 2cfaa0bbb2336e9ec18ed3ecea84fa2e2af607bc
# Content-addressed extraction avoids sharing mutable system SDK installations.
platform_dir="$sdk_cache/platform-ca5bcaa565cb37e9d287051d6dd0e49a5426ec29"
build_dir="$sdk_cache/build-tools-2cfaa0bbb2336e9ec18ed3ecea84fa2e2af607bc"
extract_once() {
    local archive="$1" destination="$2"
    if [[ ! -f "$destination/.complete" ]]; then
        [[ ! -e "$destination" ]] || { echo "Incomplete SDK directory: $destination" >&2; exit 1; }
        mkdir -p "$destination"
        unzip -q "$sdk_cache/$archive" -d "$destination"
        touch "$destination/.complete"
    fi
}
extract_once platform-31_r01.zip "$platform_dir"
extract_once build-tools_r35_linux.zip "$build_dir"
android_jar="$platform_dir/android-12/android.jar"
build_tools="$build_dir/android-15"
[[ -f "$android_jar" && -x "$build_tools/aapt2" ]] || { echo "Unexpected SDK archive layout" >&2; exit 1; }
mkdir -p "$out_dir/classes" "$out_dir/dex"
out_dir="$(cd -- "$out_dir" && pwd)"
export JAVA_HOME="$jdk_root"
export PATH="$jdk_root/bin:$PATH"
"$jdk_root/bin/javac" -encoding UTF-8 --release 8 -classpath "$android_jar" \
    -d "$out_dir/classes" "$repo_root/tools/android_probe/MainActivity.java"
mapfile -d '' class_files < <(rg --files -0 "$out_dir/classes" -g '*.class')
[[ "${#class_files[@]}" -gt 0 ]] || { echo "No compiled classes" >&2; exit 1; }
"$build_tools/d8" --min-api 31 --lib "$android_jar" --output "$out_dir/dex" "${class_files[@]}"
"$build_tools/aapt2" link -I "$android_jar" --manifest "$repo_root/tools/android_probe/AndroidManifest.xml" \
    --min-sdk-version 31 --target-sdk-version 31 --version-code 1 --version-name 0.1 \
    -o "$out_dir/unsigned.apk"
(cd "$out_dir/dex" && zip -q "$out_dir/unsigned.apk" classes.dex)
"$build_tools/zipalign" -f 4 "$out_dir/unsigned.apk" "$out_dir/aligned.apk"
key_file="$sdk_cache/probe-debug.jks"
if [[ ! -f "$key_file" ]]; then
    "$jdk_root/bin/keytool" -genkeypair -keystore "$key_file" -storepass android -keypass android \
        -alias androiddebugkey -dname 'CN=CoMi Local Probe' -keyalg RSA -keysize 2048 -validity 3650
fi
"$build_tools/apksigner" sign --ks "$key_file" --ks-key-alias androiddebugkey \
    --ks-pass pass:android --key-pass pass:android --out "$out_dir/comi-probe.apk" "$out_dir/aligned.apk"
"$build_tools/apksigner" verify --verbose "$out_dir/comi-probe.apk"
"$build_tools/aapt2" dump badging "$out_dir/comi-probe.apk"
sha256sum "$out_dir/comi-probe.apk"
