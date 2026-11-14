//! The Ithax desktop shell (spec 3 "Architecture" and "Service rules", Desktop shell;
//! AKS-142): one window that shows the interface the engine service serves.
//!
//! The window opens on the shell's own page ("Starting the engine service…"); a thread runs
//! the launcher (`launcher::run`), which finds or starts the service, and the window then
//! loads `http://127.0.0.1:<port>/v1/ui/#token=<token>`, so the interface's origin is the
//! service's own, as in a browser. The webview loads nothing else: navigation outside that
//! origin and new windows are refused, no capability is granted (no command, no plugin) and
//! the web inspector is off in a release build. Closing the window ends the shell only; the
//! service keeps its own lifetime (spec 3 "Lifetime").

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod launcher;

use std::ffi::{OsStr, OsString};
use std::sync::{Arc, Condvar, Mutex};
use std::time::Duration;

use tauri::webview::{NewWindowResponse, PageLoadEvent};
use tauri::{Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

/// The interface's address, once the launcher has printed it.
type Interface = Arc<Mutex<Option<Url>>>;

/// Set once the shell's own page has loaded, so its text can be changed.
type PageLoaded = Arc<(Mutex<bool>, Condvar)>;

/// How long a failure waits for the shell's own page to load before it is shown.
const PAGE_WAIT: Duration = Duration::from_secs(10);

fn main() {
    let options = launcher::passed_options(&std::env::args_os().skip(1).collect::<Vec<_>>());
    let python = launcher::python(launcher::python_variable(|name: &str| {
        std::env::var_os(name)
    }));
    let interface: Interface = Arc::new(Mutex::new(None));
    let page_loaded: PageLoaded = Arc::new((Mutex::new(false), Condvar::new()));
    tauri::Builder::default()
        .setup(move |app| {
            let allowed = interface.clone();
            let loaded = page_loaded.clone();
            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                    .title("Ithax")
                    .inner_size(1280.0, 800.0)
                    .min_inner_size(800.0, 600.0)
                    .devtools(cfg!(debug_assertions))
                    .on_navigation(move |target| {
                        let known = allowed.lock().map(|url| url.clone()).unwrap_or(None);
                        launcher::may_load(target, known.as_ref())
                    })
                    .on_new_window(|_, _| NewWindowResponse::Deny)
                    .on_page_load(move |_, payload| {
                        if payload.event() == PageLoadEvent::Finished
                            && launcher::may_load(payload.url(), None)
                        {
                            let (flag, signal) = &*loaded;
                            if let Ok(mut done) = flag.lock() {
                                *done = true;
                                signal.notify_all();
                            }
                        }
                    })
                    .build()?;
            let interface = interface.clone();
            let page_loaded = page_loaded.clone();
            std::thread::spawn(move || {
                open_interface(&window, &interface, &page_loaded, &python, &options)
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("the desktop shell could not start");
}

/// Runs the launcher and loads the interface in `window`, or shows why it cannot.
fn open_interface(
    window: &WebviewWindow,
    interface: &Interface,
    page_loaded: &PageLoaded,
    python: &OsStr,
    options: &[OsString],
) {
    let shown = launcher::run(python, options).and_then(|url| {
        if let Ok(mut known) = interface.lock() {
            *known = Some(url.clone());
        }
        window
            .navigate(url)
            .map_err(|error| format!("The interface could not be opened ({error})."))
    });
    if let Err(reason) = shown {
        show_failure(window, page_loaded, &reason);
    }
}

/// Puts `reason` on the shell's own page, under "The engine service did not start", once
/// that page has loaded.
fn show_failure(window: &WebviewWindow, page_loaded: &PageLoaded, reason: &str) {
    let (flag, signal) = &**page_loaded;
    if let Ok(done) = flag.lock() {
        let _ = signal.wait_timeout_while(done, PAGE_WAIT, |done| !*done);
    }
    let script = format!(
        "document.getElementById('status').textContent = {};\
         document.getElementById('detail').textContent = {};",
        serde_json::to_string("The engine service did not start").unwrap_or_default(),
        serde_json::to_string(reason).unwrap_or_default(),
    );
    let _ = window.eval(script);
}
