#!/bin/sh
# Take the AppImage as downloaded, check its checksum, and reach a first template result
# through it (#88; docs/research/m16-appimage.md), as clean_install.sh does for the archive.
# Run by tests/linux_package/test_linux_package.py:
#
#     clean_appimage.sh <folder holding the AppImage and its .sha256> <AppImage name> \
#         <python for first_result.py, or "bundled"> [--offline]
#
# In a clean container, with no FUSE, the caller sets APPIMAGE_EXTRACT_AND_RUN=1, and
# "bundled" takes the checker's Python from a copy of the AppImage extracted apart from the
# run (ubuntu:24.04 has none). It prints "step <name> <seconds since start>" lines and then
# the JSON line of first_result.py.
set -eu
from=$1
image=$2
checker=$3
shift 3
here=$(dirname "$(readlink -f "$0")")
start=$(date +%s.%N)
step() { echo "step $1 $(echo "$(date +%s.%N) - $start" | awk '{ printf "%.2f", $1 - $3 }')"; }

mkdir -p "$HOME/Downloads"
cp "$from/$image" "$from/$image.sha256" "$HOME/Downloads/"
cd "$HOME/Downloads"
step downloaded
sha256sum -c "$image.sha256" >&2
chmod 755 "$image"
step checksum

if [ "$checker" = bundled ]; then
    mkdir -p "$HOME/checker"
    (cd "$HOME/checker" && "$HOME/Downloads/$image" --appimage-extract >/dev/null)
    checker="$HOME/checker/squashfs-root/python/bin/python3"
fi

# The launcher as first_result.py calls it: the AppImage's "launcher", left in the
# background, since AppRun may stay while the service runs; its address is passed on.
cat > "$HOME/ithax-launcher" <<LAUNCHER
#!/bin/sh
out=\$(mktemp)
"$HOME/Downloads/$image" launcher "\$@" </dev/null >"\$out" 2>&1 &
pid=\$!
tries=0
until grep -q '^http' "\$out"; do
    if ! kill -0 "\$pid" 2>/dev/null || [ "\$tries" -gt 1200 ]; then
        cat "\$out" >&2
        exit 1
    fi
    tries=\$((tries + 1))
    sleep 0.1
done
grep '^http' "\$out"
LAUNCHER
chmod 755 "$HOME/ithax-launcher"
"$checker" -I "$here/first_result.py" --launcher "$HOME/ithax-launcher" "$@"
step first_result
