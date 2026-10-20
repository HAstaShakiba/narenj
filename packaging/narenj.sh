#!/bin/sh
# Ubuntu builds PyGObject for its default Python only. If /usr/bin/python3 was switched
# to another version (update-alternatives), still run Narenj with the default one.
py=$(sed -n 's/^default-version *= *//p' /usr/share/python3/debian_defaults 2>/dev/null)
exec "/usr/bin/${py:-python3}" /usr/share/narenj/narenj.py "$@"
