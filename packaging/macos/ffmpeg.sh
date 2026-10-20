# macOS (Homebrew) settings for packaging/build-ffmpeg.sh.
CC_NAME=clang
BREW="$(brew --prefix)"
# @rpath names, so ffmpeg finds its dylibs next to itself and the app bundler can relocate them;
# Homebrew's lame ships no pkg-config file, so point the compiler at Homebrew's prefix too
PLATFORM_FLAGS=(--install-name-dir='@rpath' --extra-ldexeflags='-Wl,-rpath,@loader_path'
                --extra-cflags="-I$BREW/include" --extra-ldflags="-L$BREW/lib")

collect() {  # <install-dir> <out-dir>
    cp "$1/bin/ffmpeg" "$1/bin/ffprobe" "$2/"
    cp -a "$1/lib/"*.dylib "$2/"
    strip -x "$2/ffmpeg" "$2/ffprobe"
}
