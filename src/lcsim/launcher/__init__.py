"""The launcher: how the interface finds and starts the engine service until the desktop
shell exists (spec 3 "Service rules", Launcher; AKS-119). See ``lcsim.launcher.launch``."""

from lcsim.launcher.launch import interface_url, main

__all__ = ["interface_url", "main"]
