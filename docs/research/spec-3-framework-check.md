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
