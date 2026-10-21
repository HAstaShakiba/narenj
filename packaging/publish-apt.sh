#!/bin/sh
# Publishes the .deb files in dist/ as a signed apt repository on the gh-pages branch,
# which GitHub Pages serves at https://hastashakiba.github.io/narenj/.
#
# One-time: a signing key whose user id contains "$KEY" must be in your GnuPG keyring
# (see README). Older versions already in the repository are kept.
# --dry-run builds the repository in dist/apt-site without committing or pushing.
set -e
DRY=""
[ "$1" = "--dry-run" ] && DRY=1
SRC="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${NARENJ_APT_KEY:-Narenj apt repository}"
REMOTE="$(git -C "$SRC" remote get-url origin)"
URL="https://hastashakiba.github.io/narenj"
if [ -n "$DRY" ]; then
    SITE="$SRC/dist/apt-site"
    rm -rf "$SITE"
    mkdir -p "$SITE"
else
    SITE="$(mktemp -d)"
    trap 'rm -rf "$SITE"' EXIT
fi

ls "$SRC"/dist/*.deb >/dev/null 2>&1 || { echo "No packages in dist/; run packaging/build-deb.sh first." >&2; exit 1; }
gpg --list-secret-keys "$KEY" >/dev/null 2>&1 || { echo "No GnuPG secret key matching '$KEY'." >&2; exit 1; }

if [ -n "$DRY" ]; then
    :
elif git ls-remote --exit-code --heads "$REMOTE" gh-pages >/dev/null 2>&1; then
    git clone -q --depth 1 --branch gh-pages "$REMOTE" "$SITE"
else
    git init -q -b gh-pages "$SITE"
    git -C "$SITE" remote add origin "$REMOTE"
fi
if [ -z "$DRY" ]; then
    git -C "$SITE" config user.name "$(git -C "$SRC" config user.name)"
    git -C "$SITE" config user.email "$(git -C "$SRC" config user.email)"
fi

cd "$SITE"
mkdir -p pool/main/n/narenj
cp "$SRC"/dist/*.deb pool/main/n/narenj/

# Narenj is Architecture: all, but apt asks for its own arch (and i386 on multiarch PCs), so list it there too
for arch in all amd64 arm64 i386; do
    dir="dists/stable/main/binary-$arch"
    mkdir -p "$dir"
    apt-ftparchive --arch "$arch" packages pool > "$dir/Packages"
    gzip -9nkf "$dir/Packages"
done
# old signatures would otherwise be hashed into the new Release
rm -f dists/stable/Release dists/stable/InRelease dists/stable/Release.gpg
apt-ftparchive \
    -o APT::FTPArchive::Release::Origin="Narenj" \
    -o APT::FTPArchive::Release::Label="Narenj" \
    -o APT::FTPArchive::Release::Suite="stable" \
    -o APT::FTPArchive::Release::Codename="stable" \
    -o APT::FTPArchive::Release::Architectures="all amd64 arm64 i386" \
    -o APT::FTPArchive::Release::Components="main" \
    -o APT::FTPArchive::Release::Description="Narenj, a drag-and-drop ffmpeg wheel for GNOME" \
    release dists/stable > Release.tmp
mv Release.tmp dists/stable/Release
gpg --batch --yes --local-user "$KEY" --clearsign -o dists/stable/InRelease dists/stable/Release
gpg --batch --yes --local-user "$KEY" -abs -o dists/stable/Release.gpg dists/stable/Release
gpg --export "$KEY" > narenj-archive-keyring.gpg
touch .nojekyll  # serve dists/ and pool/ as plain files

# the newest version in the pool; its GitHub release carries the Windows installer
VERSION="$(ls pool/main/n/narenj | sed -n 's/^narenj_\(.*\)_all\.deb$/\1/p' | sort -V | tail -1)"
SETUP="https://github.com/HAstaShakiba/narenj/releases/download/v$VERSION/narenj-$VERSION-setup.exe"
DMG="https://github.com/HAstaShakiba/narenj/releases/download/v$VERSION/narenj-$VERSION-macos.dmg"

# the landing page (packaging/site/index.html) with this version's download links, its icon and
# the wheel pictures, drawn by Narenj itself (needs PyGObject, like Narenj)
sed -e "s|@VERSION@|$VERSION|g" -e "s|@SETUP@|$SETUP|g" -e "s|@DMG@|$DMG|g" -e "s|@URL@|$URL|g" \
    "$SRC/packaging/site/index.html" > index.html
cp "$SRC/narenj.svg" icon.svg
mkdir -p screenshots
rm -f screenshots/*.png
# the distribution's own Python, which has PyGObject even when python3 points elsewhere
PY="$(sed -n 's/^default-version *= *//p' /usr/share/python3/debian_defaults 2>/dev/null)"
"${PY:-python3}" "$SRC/packaging/site/render-wheels.py" screenshots

if [ -n "$DRY" ]; then
    echo "Built $SITE (not published)."
    exit 0
fi
git add -A
if git diff --cached --quiet; then
    echo "Repository already up to date."
    exit 0
fi
git commit -q -m "Publish $(ls pool/main/n/narenj | tr '\n' ' ')"
git push -q origin gh-pages
echo "Published to $URL"
