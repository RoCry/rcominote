# List named verbs; success changes no files or devices.
[private]
default:
    @just --list

# Green means formatting, lint, shell syntax, and offline tests pass.
[group('dev')]
check:
    bash tools/check.sh
