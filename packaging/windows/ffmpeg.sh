# Windows (MSYS2 UCRT64) settings for packaging/build-ffmpeg.sh.
CC_NAME=gcc
PLATFORM_FLAGS=()

collect() {  # <install-dir> <out-dir>
    cp "$1/bin/"*.exe "$1/bin/"*.dll "$2/"
    strip "$2/"*.exe "$2/"*.dll
}
