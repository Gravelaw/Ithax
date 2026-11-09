#!/bin/sh
# Remove what install.sh added: the command links that point into this folder and the
# desktop entry. Projects and settings stay (~/.local/share/lcsim and ~/.config/lcsim, or
# under $XDG_DATA_HOME and $XDG_CONFIG_HOME); delete this folder yourself afterwards.
set -eu
root=$(dirname "$(readlink -f "$0")")
bin_dir="$HOME/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
case "$apps_dir" in /*) ;; *) apps_dir="$HOME/.local/share/applications" ;; esac

for name in lcsim lcsim-launcher lcsim-mcp; do
    link="$bin_dir/$name"
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$root/bin/$name" ]; then
        rm -f "$link"
        echo "Removed $link"
    fi
done
entry="$apps_dir/lcsim.desktop"
if [ -f "$entry" ] && grep -qF "Exec=\"$root/bin/lcsim\"" "$entry"; then
    rm -f "$entry"
    echo "Removed $entry"
fi
echo "Your projects and settings are kept. You may now delete $root"
