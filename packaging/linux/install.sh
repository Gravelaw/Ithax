#!/bin/sh
# Install lcsim from this unpacked folder, for the current user (spec 3 "Packaging";
# AKS-127). No administrator rights and no network are needed: this folder already holds
# everything. It checks the bundled Python and engines, links the commands into
# ~/.local/bin and adds a desktop entry. Run it again after moving the folder.
set -eu
root=$(dirname "$(readlink -f "$0")")
bin_dir="$HOME/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
case "$apps_dir" in /*) ;; *) apps_dir="$HOME/.local/share/applications" ;; esac

unset PYTHONHOME PYTHONPATH
export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
python="$root/python/bin/python3"

echo "Checking the bundled Python, engines, interface and templates..."
if ! "$python" -m lcsim.install_check; then
    echo "The check failed: this folder is incomplete or does not run on this machine." >&2
    exit 1
fi

mkdir -p "$bin_dir"
for name in lcsim lcsim-launcher lcsim-mcp; do
    ln -sfn "$root/bin/$name" "$bin_dir/$name"
done
echo "Linked lcsim, lcsim-launcher and lcsim-mcp into $bin_dir"

mkdir -p "$apps_dir"
cat > "$apps_dir/lcsim.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=lcsim
Comment=Model, simulate and optimize processes without writing code
Exec="$root/bin/lcsim"
Icon=$root/share/lcsim.png
Terminal=false
Categories=Education;Science;Engineering;
EOF
echo "Added the desktop entry $apps_dir/lcsim.desktop"

if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    echo "No display is set here: use 'lcsim-launcher --print-url' to get the interface's address."
elif missing=$(ldd "$root/lib/lcsim-desktop" 2>/dev/null | grep "not found"); then
    echo "The desktop shell's system libraries are missing, so 'lcsim' opens the interface in"
    echo "the browser. To get the desktop window (Ubuntu or Debian):"
    echo "  sudo apt install libwebkit2gtk-4.1-0"
    echo "$missing"
else
    echo "'lcsim' opens the desktop window."
fi
case ":$PATH:" in
    *":$bin_dir:"*) echo "Done. Start it with: lcsim" ;;
    *) echo "Done. $bin_dir is not on your PATH; start it with: $bin_dir/lcsim" ;;
esac
