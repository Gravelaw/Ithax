# M16 research: an AppImage of the Linux package (#88)

## Question

#88 (owner decision B5, 2026-11-13) asks for an AppImage for Linux, "double-click install, built from the existing Tauri tree". Which tool builds it, under which licence, at which pinned version, and how does it fit `scripts/package_linux.py`, which builds the self-contained archive today (`docs/research/spec-3-linux-packaging.md`, option A)?

## Finding

Read on 2026-11-15:

- **appimagetool** ("a low-level tool to generate an AppImage from an existing AppDir"; <https://github.com/AppImage/appimagetool>). MIT ("Copyright (c) 2004-25 Simon Peter and the AppImage Team", its `LICENSE`).
  - It is published on GitHub Releases as `appimagetool-x86_64.AppImage`.
  - The releases page shows tagged versions 1.9.0 and 1.9.1 and a rolling `continuous` build. The page shows dates without years.
  - It downloads the latest runtime at build time unless one is given with `--runtime-file`, or with `APPIMAGETOOL_RUNTIME_FILE`; the option wins over the variable.
  - Its README says nothing about reproducible builds or `SOURCE_DATE_EPOCH`.
- **type2-runtime**, the executable part of every AppImage, which "mounts the payload via FUSE and executes the entrypoint" (<https://github.com/AppImage/type2-runtime>). MIT ("Copyright (c) 2004-23 probonopd", its `LICENSE`).
  - It is statically linked (built on Alpine with musl), so "libfuse2 is no longer required on the target system". This removes the objection of 2026-11-09, that an AppImage needs FUSE 2, which Ubuntu 22.04 and later lack.
  - Its releases page shows a dated tag `20251108`, an `old` tag and a rolling `continuous` build, with `runtime-x86_64` (922 KB).
  - The runtime ships inside every AppImage, so its MIT notice goes into `THIRD-PARTY-LICENSES.txt` and the licence list.
- **FUSE on the user's machine** (<https://docs.appimage.org/user-guide/troubleshooting/fuse.html>): recent Ubuntu ships `fuse3` by default. Where FUSE cannot be used, as in a container, `--appimage-extract-and-run` or `APPIMAGE_EXTRACT_AND_RUN=1` "extracts the AppImage, runs the contents, waits until the app closes, and then cleans up". The variable is usually passed on to child processes, which the service's run workers are.
- **Tauri's own AppImage bundle** is not used. It bundles WebKitGTK and GTK, which makes it larger, and it would still need the Python tree (option B of 2026-11-09). #88's "built from the existing Tauri tree" is met by putting the shell that `desktop/` already builds into the AppImage.
- **The package tree is already an AppDir in all but name.** `bin/ithax` finds its folder with `readlink -f "$0"`. The bundled Python is relocatable. The service finds the interface and templates under `sys.prefix`. Bytecode is compiled at build time, so a read-only mount needs no writes. Only three files are missing: `AppRun`, a `.desktop` file and an icon at the top level.

## Decision

Proposed (owner to confirm; Phase 1a, #88):

- **Tool.** appimagetool 1.9.1 with type2-runtime `20251108`, each downloaded once by `scripts/package_linux.py` into `dist/cache`, as the Python archive is. Each is checked against a pinned SHA-256, and the runtime is given with `--runtime-file`, so nothing is fetched unpinned. Both are MIT and are build tools, except the runtime, which ships and is listed.
- **Layout.** The staged package folder becomes the AppDir, with three files added:
  - `AppRun`, which runs `bin/ithax`; `ithax-<version>-x86_64.AppImage mcp` and `... launcher` run `bin/ithax-mcp` and `bin/ithax-launcher`.
  - `ithax.desktop`.
  - `ithax.png`.
- **Output.** `dist/ithax-<version>-x86_64.AppImage`, with a `.sha256` file beside it as for the archive. Unsigned, with the checksum documented (spec 0 "Risks"). The archive stays: it installs commands and a desktop entry, and runs where FUSE does not.
- **Tests (`pytest -m package`).**
  - The AppImage file is an ELF with the runtime's magic bytes.
  - Extracted with `--appimage-extract`, it holds the same tree as the archive.
  - In a clean `ubuntu:24.04` container with `APPIMAGE_EXTRACT_AND_RUN=1`, it reaches the coffee shop's first result through `/v1`, offline.
- **Same bytes.** Two builds of one commit must give the same AppImage, as the archive does. appimagetool's README does not promise this, so the test decides. If its squashfs is not reproducible, the build gives `mksquashfs` fixed times through `SOURCE_DATE_EPOCH`, or the gap is recorded.

## Not tested here

The SHA-256 pins could not be taken in the agent container:

- `github.com` answers 403 there, since this session reaches GitHub only through its integration.
- No package registry (PyPI, npm, crates.io) carries appimagetool or the runtime.
- No Python archive is cached in `dist/cache`, so the package itself cannot be built here either.

The `package` CI job downloads from GitHub today. So the pins come from one of:

- **A. CI prints them.** A one-off step in the `package` job prints the SHA-256 of the two pinned downloads, and they are copied from its log, with the run ID.
- **B. The owner pins them.** The owner downloads the two files once and gives their SHA-256.

Until one of these is done, the build cannot be run or its tests seen passing. The research note's other facts were read from the pages named above.

**Pinned (2026-11-15, option A).** PR #210 gave the `package` job a lasting step, `python scripts/package_linux.py --check-appimage-tools`. It downloads both tools by their exact release URLs, prints each SHA-256, and compares it with the digest the GitHub release publishes for the asset. Once pins are recorded, it also compares with them and fails on any difference. In CI run 43752479955 (head `1751cb7`) both hashes matched their releases' published digests:

- appimagetool 1.9.1: `ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`;
- type2-runtime `20251108`: `2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d`.

The pins are the hashes CI computed, checked against the published digests, which both releases list. They are recorded in `scripts/package_linux.py` and `docs/DECISIONS.md`.

## Sources

- <https://github.com/AppImage/appimagetool>, its `LICENSE` and its releases page.
- <https://github.com/AppImage/type2-runtime>, its `LICENSE` and its releases page.
- <https://docs.appimage.org/user-guide/troubleshooting/fuse.html>.
- `docs/research/spec-3-linux-packaging.md` (2026-11-09), `scripts/package_linux.py`, `packaging/linux/bin/ithax`.
