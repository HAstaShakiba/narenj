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

cat > index.html <<HTML
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Narenj apt repository</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:3rem auto;padding:0 1rem}
pre{background:#f4f4f5;padding:1rem;border-radius:8px;overflow-x:auto}</style></head>
<body><h1>Narenj</h1>
<p>A drag-and-drop ffmpeg wheel for GNOME. Source: <a href="https://github.com/HAstaShakiba/narenj">github.com/HAstaShakiba/narenj</a></p>
<h2>Install on Ubuntu / Debian</h2>
<pre>sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL $URL/narenj-archive-keyring.gpg | sudo tee /etc/apt/keyrings/narenj.gpg &gt;/dev/null
echo "deb [signed-by=/etc/apt/keyrings/narenj.gpg] $URL stable main" | sudo tee /etc/apt/sources.list.d/narenj.list
sudo apt update
sudo apt install narenj
narenj --setup</pre>
<p>Then log out and back in once so GNOME Shell loads the always-on-top extension.</p>
</body></html>
HTML

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
