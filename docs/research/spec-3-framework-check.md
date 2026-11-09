# Spec 3 research: framework check

## Question

What are the current state, licence, and Linux and Windows support of the interface frameworks named or considered in spec 3 "Architecture": Tauri, Electron, Qt and React Flow? Is each compatible with the product's AGPL-3.0 licence? (Spec 3, "Research before building", M6 (service) and M9 (interface) · Framework check.)

This note covers the **interface part**, checked at the M9 design session on 2026-11-06. The service part (FastAPI) is checked at M6 and is added to this note then.

## Finding

| Framework | Role | Current version (release date) | Licence | Linux | Windows |
| --- | --- | --- | --- | --- | --- |
| Tauri 2 (`tauri` crate, `@tauri-apps/cli`, `@tauri-apps/api`) | Desktop shell around the system webview | crate 2.12.5 (2026-10-21); CLI 2.12.4 (2026-10-21); API 2.12.4 (2026-10-14) | Apache-2.0 OR MIT (crates.io and npm metadata); README: "MIT or MIT/Apache 2.0 where applicable" | Yes: needs WebKitGTK 4.1 ("webkit2gtk 4.1 for Tauri v2 (for example Ubuntu 22.04)"); prerequisites listed for Debian, Arch, Fedora, Gentoo, OSTree, openSUSE, Alpine and NixOS | Yes: Windows 10 and later in the README table; uses Microsoft Edge WebView2, preinstalled on Windows 10 version 1803 and later, otherwise installed with the Evergreen Bootstrapper |
| `wry`, `tao` (Tauri's webview and window crates) | Pulled in by Tauri | wry 0.57.1, tao 0.37.2 (both 2026-10-23) | wry Apache-2.0 OR MIT; tao Apache-2.0 (crates.io metadata of the newest version) | | |
| Electron | Desktop shell with its own Chromium | 45.2.3 (2026-11-04) | MIT | x64 and arm64; "major Linux distributions (e.g., Ubuntu, Fedora, Debian)" | Windows 10 and later, x64 and arm64 |
| Qt 6 for Python (PySide6) | Native widget toolkit | 6.12.0 (wheels uploaded 2026-10-08) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only (PyPI metadata); some Qt modules are GPL-3.0 only, among them Qt Graphs, Qt Quick 3D, Qt Virtual Keyboard and Qt HTTP Server | manylinux x86_64 and aarch64 wheels | win_amd64 and win_arm64 wheels |
| PyQt6 | Alternative Qt binding | 6.12.0 (2026-10-28) | GPL-3.0-only (PyPI metadata) | Yes | Yes |
| React Flow (`@xyflow/react`) | Node-editor library inside the webview | 12.12.1 (2026-11-02) | MIT (npm metadata; repository `LICENSE`, copyright webkid GmbH) | Runs in any modern webview | Same |
| React | User-interface library | 19.3.1 (2026-10-14) | MIT (npm metadata) | Same | Same |
| WebKitGTK (system library used by Tauri on Linux) | Webview on Linux | 2.54.2 (2026-10-23) | WebKit is "open source software with portions licensed under the LGPL and BSD licenses" (webkit.org) | Distribution package, not shipped by the product | |

Other facts that bear on the choice:

- **Tauri security advisory.** GHSA-7gmj-67g7-phm9 (CVE-2026-42184): on Windows and Android, Tauri 2.0 to 2.11.0 can treat a remote page such as `http://app.evil.com/` as the app's own local origin and let it call backend commands. Fixed in 2.11.1. The product must require Tauri 2.11.1 or later.
- **Tauri origin on Windows.** On Windows and Android, Tauri serves the app's custom protocol as `http://<scheme>.localhost/` (the advisory), and since Tauri 2.1.0 the option `app > windows > useHttpsScheme` switches it to `https://`. The Linux origin was not found in the pages read. Spec 3's WebSocket `Origin` rule ("fixed at M9") is therefore set and tested on both platforms when the interface is built.
- **End-to-end testing.** Tauri's WebDriver guide says `tauri-driver` drives "the platform's native WebDriver ... on Windows and Linux"; macOS has no WKWebView driver. This answers spec 3's note that `tauri-driver` availability on Linux was unverified, as far as documentation goes; it has not been run.
- **Electron support window.** "The latest three stable major versions are supported", with a new major version every eight weeks, so an Electron app must upgrade its Chromium at least every six months or so to stay supported.
- **React Flow attribution.** The library renders a small attribution link and asks that it be removed only by subscribers (`proOptions`). The MIT licence does not require it; the product keeps it.
- **Rendering differences.** Tauri uses two different engines, WebKitGTK on Linux and WebView2 (Chromium) on Windows. Electron ships one engine everywhere. The pointer-only end-to-end test (spec 3) must therefore run on both platforms.

### Licence compatibility with AGPL-3.0

Not legal advice; a lawyer confirms before the first public release (spec 0).

- **MIT and Apache-2.0** (Tauri, wry, tao, React, React Flow, Electron) are permissive. Code under them can be combined into an AGPL-3.0 work. The Apache Software Foundation records that the Free Software Foundation considers Apache-2.0 compatible with GPLv3 (but not GPLv2); this note takes AGPL-3.0, which belongs to the same version 3 family, to follow, and a lawyer confirms. For the dual-licensed crates the MIT option removes the question; `tao` is Apache-2.0 only.
- **Qt** (LGPL-3.0, GPL-2.0 or GPL-3.0 per module) is not chosen, so its compatibility is not argued here; Qt's own licensing FAQ pages returned "not found" when read.
- **WebKitGTK (LGPL and BSD) and WebView2** are system components on their platforms. The product loads them and does not ship or modify them. The owner's lawyer should confirm the system-library reading for WebView2, which is proprietary Microsoft software.

## Sources

Read on 2026-11-06. The registry and crates.io endpoints were read with a script; the pages were read in a browser fetch.

- npm registry: https://registry.npmjs.org/electron, https://registry.npmjs.org/@xyflow/react, https://registry.npmjs.org/react, https://registry.npmjs.org/@tauri-apps/cli, https://registry.npmjs.org/@tauri-apps/api
- crates.io API: https://crates.io/api/v1/crates/tauri, https://crates.io/api/v1/crates/wry, https://crates.io/api/v1/crates/tao
- PyPI JSON: https://pypi.org/pypi/PySide6/json, https://pypi.org/pypi/PyQt6/json
- Tauri README (platform table, licence): https://github.com/tauri-apps/tauri/blob/dev/README.md
- Tauri prerequisites: https://v2.tauri.app/start/prerequisites/
- Tauri 2.1.0 release notes (`useHttpsScheme`): https://v2.tauri.app/release/tauri/v2.1.0/
- Tauri WebDriver testing: https://v2.tauri.app/develop/tests/webdriver/
- Tauri security advisory GHSA-7gmj-67g7-phm9: https://github.com/tauri-apps/tauri/security/advisories/GHSA-7gmj-67g7-phm9
- Electron README (platforms, licence): https://github.com/electron/electron/blob/main/README.md
- Electron release timelines: https://www.electronjs.org/docs/latest/tutorial/electron-timelines
- Qt 6 licensing: https://doc.qt.io/qt-6/licensing.html
- React Flow licence: https://github.com/xyflow/xyflow/blob/main/LICENSE
- React Flow API reference (`proOptions`, `minZoom`, `maxZoom`, `onlyRenderVisibleElements`): https://reactflow.dev/api-reference/react-flow
- WebKitGTK home page (current release): https://webkitgtk.org/
- WebKit licensing: https://webkit.org/licensing-webkit/
- Apache Software Foundation, "Apache License v2.0 and GPL Compatibility": https://www.apache.org/licenses/GPL-compatibility.html

## Decision

**Interface: confirmed as written in spec 3 "Architecture":** React with React Flow (`@xyflow/react`), packaged as a desktop app with Tauri 2, at version 2.11.1 or later.

- **Why Tauri over Electron.** Both work on Linux and Windows under permissive licences. Tauri uses the webview the system already has, so the product does not ship and update a browser engine on Electron's eight-week cadence; that suits a single maintainer (spec 0, risks). The cost is two rendering engines, and that is covered by running the end-to-end test on both platforms. Electron remains the fallback if WebKitGTK proves unworkable on the low tier; that would be a DECISIONS entry and a spec change.
- **Why not Qt.** React Flow already provides the node editor, with keyboard support and an accessibility layer. A Qt interface would need its own node editor, and the interface would no longer be a client of the HTTP API like any other client (spec 3: "The interface uses no private channel").
- **Not added now.** No interface code exists, so `DECISIONS.md` records these packages without adding them. Versions are pinned when M9 code starts.

## Tested

Facts were read from registries and documentation, not tested by building an app: no `ui/` code exists in this session (AKS-118 is documents only). The first M9 coding session builds a minimal Tauri window on Linux and Windows before anything else, and records the result here.

2026-11-08, M9 (AKS-119): re-checked before pinning, from the npm registry (`npm view <package>@<version> time license`) and crates.io, and the `LICENSE` file of each installed package read. Nothing moved since 2026-11-06: React 19.3.1 (2026-10-14, MIT), `@xyflow/react` 12.12.1 (2026-11-02, MIT), Tauri crate 2.12.5 and `@tauri-apps/cli` and `@tauri-apps/api` 2.12.4 (Apache-2.0 OR MIT), ECharts 6.1.0 (Apache-2.0, for a later ticket). React, React DOM and `@xyflow/react` are now pinned in `ui/package.json`, with the rest of the interface's toolchain (`docs/DECISIONS.md`, 2026-11-08 · M9). **The minimal Tauri window was not built:** WebKitGTK, which Tauri needs on Linux, cannot be installed in the agent container, and no Windows machine is available to the agent. The React interface is built and tested in Chromium (Playwright) against the real service instead, served by the service itself; the Tauri shell, its origin and `tauri-driver` are logged as an engine gap in `docs/DECISIONS.md` and left for M11 packaging unless the M9 close (AKS-121) can build it in CI.

2026-11-08, M9 close (AKS-121): the end-to-end driver. Tauri's WebDriver page (`https://v2.tauri.app/develop/tests/webdriver/`, last updated 2026-06-29, read 2026-11-08) says `tauri-driver` drives the platform's native WebDriver "on Windows and Linux" (on Linux WebKitGTK's driver, on Windows Edge's), and that "only Windows and Linux are supported on desktop, as macOS has no WKWebView driver tool available"; WebdriverIO's `@wdio/tauri-service` and CrabNebula's fork add macOS. So `tauri-driver` is available on Linux per the documentation, but it drives a built Tauri app, and this container has no WebKitGTK and no `WebKitWebDriver` (checked with `which` and the system libraries), so it was not run. The pointer-only end-to-end test is written in Playwright 1.63.0 with Chromium against the real service serving the interface (`ui/e2e/pointer-only.spec.ts`); `tauri-driver` and the desktop shell stay for M11 (`docs/DECISIONS.md`, "Engine gap: Tauri lacks a build in the agent container").

## 2026-11-09 re-check, M11 (AKS-142): Tauri 2 on Linux

### Question

Before building the desktop shell: what is Tauri 2's current release, and is it at 2.11.1 or later (advisory GHSA-7gmj-67g7-phm9) with no newer advisory? What does it need on Linux (WebKitGTK 4.1 and the other system packages), and can those be installed here? Do `tauri-driver` and `WebKitWebDriver` exist and run on Linux? What are the licences of the crates and the CLI?

### Finding

- **Releases (crates.io API and npm registry, read 2026-11-09).** `tauri` 2.12.5 (2026-10-21) is the newest 2.x; 3.0.0-alpha.6 (2026-11-06) is a pre-release and not used. `tauri-build` 2.7.4 (2026-10-21), `tauri-runtime-wry` 2.12.3, `wry` 0.57.1, `tao` 0.37.2 (both 2026-10-23), `@tauri-apps/cli` 2.12.4 (2026-10-21), `tauri-driver` 2.1.0 (2026-09-26; 3.0.0-alpha.1 is a pre-release). Nothing moved since the 2026-11-08 re-check.
- **Advisories (OSV API, `crates.io` and `npm` ecosystems, read 2026-11-09).** For the `tauri` crate the newest is GHSA-7gmj-67g7-phm9 (CVE-2026-42184, published 2026-05-06, affected 2.0.0 to before 2.11.1); every other one affects 1.x or a 2.0 pre-release. `wry`, `tao`, `tauri-runtime-wry`, `tauri-utils`, `tauri-build` and `tauri-codegen` have none. `@tauri-apps/cli` has only GHSA-2rcp-jvr4-r259, a misconfiguration of the updater's private key with Vite in Tauri 1 guides, which does not apply (no updater, no Vite build in the shell). 2.12.5 is therefore at or above every fix.
- **Linux requirements.** Tauri's prerequisites page (last updated 2026-08-20) lists for Debian and Ubuntu: `libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev`; WebKitGTK 4.1 throughout. In this container (Ubuntu 24.04.5) every one installs through apt; `libwebkit2gtk-4.1-dev` is 2.52.6-0ubuntu0.24.04.1 (noble-updates and noble-security). The built shell links only `libwebkit2gtk-4.1`, `libjavascriptcoregtk-4.1`, `libgtk-3` and `libsoup-3.0` of these (`ldd`), since it has no tray icon and no menu.
- **WebDriver on Linux.** Tauri's manual WebDriver setup page (last updated 2026-06-29): "We use `WebKitWebDriver` on Linux platforms", packaged separately on Debian as `webkit2gtk-driver`; `tauri-driver` is installed with `cargo install tauri-driver --locked`. Ubuntu 24.04 has `webkit2gtk-driver` 2.52.6, which installs `/usr/bin/WebKitWebDriver`. `tauri-driver` 2.1.0's source: it listens on 4444 by default (`--port`), runs the native driver on 4445 (`--native-port`, `--native-driver PATH`), reads the capability `tauri:options` with `application` (the binary) and `args`, passes them to WebKitWebDriver as `webkitgtk:browserOptions`, and sets `TAURI_WEBVIEW_AUTOMATION=true` for the app.
- **Licences.** `tauri`, `tauri-build`, `tauri-runtime-wry`, `wry`, `tauri-driver` and `@tauri-apps/cli`: Apache-2.0 OR MIT; `tao`: Apache-2.0 (crates.io and npm metadata, and `cargo metadata` of the lock file). Of the 403 crates `Cargo.lock` resolves, for every platform, each licence is MIT, Apache-2.0, BSD-3-Clause, ISC, Zlib, Unicode-3.0, Unlicense, CC0-1.0 or 0BSD alone or as an option, except five MPL-2.0 crates (`cssparser`, `cssparser-macros`, `selectors`, `dtoa-short`, pulled in by `tauri-utils` for HTML processing at build time, and `option-ext`, pulled in by `dirs`) and two offering LGPL-2.1-or-later among MIT and Apache-2.0 (`r-efi`, UEFI only). None has a licence that is missing.
- **MPL-2.0 and AGPL-3.0.** MPL-2.0 section 3.3 lets a "Larger Work" combine MPL code with code under the GNU GPL, LGPL or AGPL ("Secondary Licenses", section 1.12) unless the code carries Exhibit B, "Incompatible With Secondary Licenses"; no file of the five crates carries that notice outside the licence text itself (searched in Cargo's registry folder, 2026-11-09). The MPL files stay under the MPL.

### Sources

Read on 2026-11-09, the registry and API endpoints with `curl` and `npm view`, the pages with a fetch.

- crates.io API: https://crates.io/api/v1/crates/tauri, `tauri-build`, `tauri-driver`, `wry`, `tao`, `tauri-runtime-wry`
- npm registry: `npm view @tauri-apps/cli version time license`
- OSV API (`POST https://api.osv.dev/v1/query`) for `tauri`, `tauri-runtime-wry`, `wry`, `tao`, `tauri-utils`, `tauri-build`, `tauri-codegen` (crates.io) and `@tauri-apps/cli` (npm)
- Tauri prerequisites: https://v2.tauri.app/start/prerequisites/
- Tauri WebDriver testing: https://v2.tauri.app/develop/tests/webdriver/ and https://v2.tauri.app/develop/tests/webdriver/manual-setup/
- `tauri-driver` 2.1.0 source (`src/cli.rs`, `src/server.rs`, `src/webdriver.rs`), from Cargo's registry after `cargo install`
- `tauri` 2.12.5 source (`src/webview/mod.rs`: `on_navigation`, `on_new_window`, `navigate`, `devtools` "requires `devtools` feature flag to enable it in release builds")
- Ubuntu archive through `apt-cache policy`, and each package's `/usr/share/doc/<package>/copyright`
- Mozilla Public License 2.0, sections 1.12 and 3.3: https://www.mozilla.org/en-US/MPL/2.0/

### Decision

The shell is built with `tauri` 2.12.5, `tauri-build` 2.7.4 and `@tauri-apps/cli` 2.12.4, pinned exactly and by `Cargo.lock` and `desktop/package-lock.json`, and driven with `tauri-driver` 2.1.0 and Ubuntu's `WebKitWebDriver` 2.52.6. The shell loads the interface from the service (`http://127.0.0.1:<port>/v1/ui/`), so its webview's origin is the service's own and the service's allowed origins do not change (spec 3 "Service rules", Desktop shell). Licences and the system packages are recorded in `docs/DECISIONS.md` (2026-11-09 · M11, AKS-142).

### Tested

2026-11-09, M11 (AKS-142), in the agent container (Ubuntu 24.04.5, Rust 1.97.0, Node 22): the system packages installed with apt; `cargo install tauri-driver --version 2.1.0 --locked` built it; `npm run build` in `desktop/` (`tauri build --no-bundle -- --locked`) built the release shell (3.5 MB) in 2 min 18 s from cold; `cargo test --locked` passed its 13 unit tests; and `pytest -m desktop` (`tests/desktop/test_shell.py`) passed both tests in under 8 s: under Xvfb, through `tauri-driver` and `WebKitWebDriver`, the shell started a real service through the launcher, showed the first-start notice, saved it with Continue and reached Home; the window's address was `http://127.0.0.1:<port>/v1/ui/`; the token was on no process's command line; a navigation to another port of 127.0.0.1, a `window.open` and a clicked `target="_blank"` link loaded nothing and opened no window; closing the window ended the shell and the service still answered; and with a Python that does not exist, the shell's own page said why. Two mutations were tried and each failed the test: navigation allowed everywhere (the other server was asked for `/navigated`), and new windows allowed (two window handles after the click). A `window.open` from a script opened no window even with new windows allowed (WebKitGTK does not let a script open one by default), so the test also clicks a link. Two findings about the driver, from the first runs: `tauri-driver` 2.1.0 forwards requests to `WebKitWebDriver` through a connection pool that does not retry, and when the client's request says `Connection: close` (as each of Python's `urllib` requests does) `WebKitWebDriver` closes its end after answering; the pool then now and then sent the next request on the closing connection, and `tauri-driver` dropped the client's connection without an answer (about one call in ten, more under load; seen with `strace` on `WebKitWebDriver`: no request arrived, and the next call went through). The test therefore keeps one connection alive (`http.client`), after which 15 runs of `pytest -m desktop` in a row passed. And ending the session while the shell is open sometimes left the shell running after `tauri-driver` stopped, so the test closes the window first (`DELETE /session/{id}/window`), as the user does, and checks that the shell ends and the service still answers.
