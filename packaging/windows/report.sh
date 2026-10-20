#!/usr/bin/env bash
# Runs a command and, if it fails, publishes the end of its output as a GitHub Actions error
# annotation, which (unlike job logs) can be read without signing in.
#   packaging/windows/report.sh "<title>" <command> [args...]
title="$1"; shift
"$@" > report.log 2>&1
rc=$?
cat report.log
if [ "$rc" -ne 0 ]; then
    msg="$(tail -c 3500 report.log | tr -d '\r' | sed -e 's/%/%25/g' | sed -e ':a;N;$!ba;s/\n/%0A/g')"
    echo "::error title=$title::$msg"
fi
exit "$rc"
