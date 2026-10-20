#!/usr/bin/env bash
# Runs a command and, if it fails, publishes the end of its output as a GitHub Actions error
# annotation, which (unlike job logs) can be read without signing in. Used on Windows and macOS.
#   packaging/windows/report.sh "<title>" <command> [args...]
title="$1"; shift
"$@" > report.log 2>&1
rc=$?
cat report.log
if [ "$rc" -ne 0 ]; then
    msg="$(tail -c 3500 report.log | tr -d '\r' | awk '{gsub(/%/, "%25"); printf "%s%%0A", $0}')"
    echo "::error title=$title::$msg"
fi
exit "$rc"
