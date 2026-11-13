#!/bin/sh
# Inside a clean container, as an ordinary user: take the package as downloaded, check its
# checksum, unpack, install and reach a first template result (spec 3 acceptance, M11;
# AKS-127). Run by tests/linux_package/test_linux_package.py:
#
#     clean_install.sh <folder holding the archive and its .sha256> <archive name> [--offline]
#
# It prints, on standard output, one line per step "step <name> <seconds since start>" and
# then the JSON line of first_result.py.
set -eu
from=$1
archive=$2
shift 2
name=${archive%.tar.gz}
here=$(dirname "$(readlink -f "$0")")
start=$(date +%s.%N)
step() { echo "step $1 $(echo "$(date +%s.%N) - $start" | awk '{ printf "%.2f", $1 - $3 }')"; }

mkdir -p "$HOME/Downloads"
cp "$from/$archive" "$from/$archive.sha256" "$HOME/Downloads/"
cd "$HOME/Downloads"
step downloaded
sha256sum -c "$archive.sha256" >&2
step checksum
mkdir -p "$HOME/.local/opt"
tar -xzf "$archive" -C "$HOME/.local/opt"
step unpacked
"$HOME/.local/opt/$name/install.sh" >&2
step installed
"$HOME/.local/opt/$name/python/bin/python3" -I "$here/first_result.py" \
    --launcher "$HOME/.local/bin/lcsim-launcher" "$@"
step first_result
