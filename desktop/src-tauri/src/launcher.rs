//! How the shell reaches the engine service: it runs the launcher, `python -m ithax.launcher
//! --print-url`, and reads the interface's address from its output (spec 3 "Service rules",
//! Launcher and Desktop shell; AKS-142). The launcher finds the running service through
//! `service.json` and its probe, or starts one and waits up to 30 seconds for it, so none of
//! that logic is repeated here. The address, with its token, comes back on a pipe that only
//! the shell reads, never on a command line.

use std::ffi::{OsStr, OsString};
use std::process::{Command, Stdio};

use tauri::Url;

/// The environment variable naming the Python that has `lcsim` installed, as for the
/// interface's end-to-end tests (`ui/e2e/service.ts`).
pub const PYTHON_VARIABLE: &str = "LCSIM_PYTHON";

/// The launcher's options the shell passes on; each takes one value.
pub const PASSED_OPTIONS: [&str; 4] = ["--config-dir", "--data-dir", "--ui-dir", "--idle-minutes"];

/// The Python to run: `LCSIM_PYTHON` when set and not empty, else `python3` (`python` on
/// Windows), found on the search path.
pub fn python(variable: Option<OsString>) -> OsString {
    match variable {
        Some(value) if !value.is_empty() => value,
        _ if cfg!(windows) => OsString::from("python"),
        _ => OsString::from("python3"),
    }
}

/// The launcher options among the shell's own arguments: each of [`PASSED_OPTIONS`] with its
/// value, as `--name value` or `--name=value`. Anything else is not the launcher's (a
/// WebDriver or the desktop may add arguments of its own) and is left out.
pub fn passed_options(arguments: &[OsString]) -> Vec<OsString> {
    let mut passed = Vec::new();
    let mut index = 0;
    while index < arguments.len() {
        let argument = arguments[index].to_string_lossy();
        if PASSED_OPTIONS.contains(&argument.as_ref()) {
            if let Some(value) = arguments.get(index + 1) {
                passed.push(arguments[index].clone());
                passed.push(value.clone());
            }
            index += 2;
            continue;
        }
        if let Some((name, _)) = argument.split_once('=') {
            if PASSED_OPTIONS.contains(&name) {
                passed.push(arguments[index].clone());
            }
        }
        index += 1;
    }
    passed
}

/// The launcher's arguments: the module, the passed options, and `--print-url`.
pub fn launcher_arguments(options: &[OsString]) -> Vec<OsString> {
    let mut arguments: Vec<OsString> = vec!["-m".into(), "ithax.launcher".into()];
    arguments.extend(options.iter().cloned());
    arguments.push("--print-url".into());
    arguments
}

/// The interface's address in the launcher's output: its last line that is not empty, when
/// it is `http://127.0.0.1:<port>/v1/ui/` with a fragment holding the token, as the launcher
/// prints it; `None` otherwise.
pub fn interface_url(output: &str) -> Option<Url> {
    let line = output.lines().rev().find(|line| !line.trim().is_empty())?;
    let url = Url::parse(line.trim()).ok()?;
    let fragment = url.fragment().unwrap_or("");
    let ok = url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && url.port().is_some()
        && url.path() == "/v1/ui/"
        && url.query().is_none()
        && fragment.starts_with("token=")
        && fragment.len() > "token=".len();
    ok.then_some(url)
}

/// Runs the launcher with `python` and returns the interface's address, or the reason
/// there is none, in words for the shell's page.
pub fn run(python: &OsStr, options: &[OsString]) -> Result<Url, String> {
    let output = Command::new(python)
        .args(launcher_arguments(options))
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|error| {
            format!(
                "{} could not be run ({error}). Set {PYTHON_VARIABLE} to the Python that has \
                 lcsim installed.",
                python.to_string_lossy()
            )
        })?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        let said = stderr.trim();
        return Err(if said.is_empty() {
            format!("The launcher stopped ({}).", output.status)
        } else {
            said.to_string()
        });
    }
    interface_url(&stdout).ok_or_else(|| {
        "The launcher did not print the interface's address. Check that the lcsim package \
         is installed for this Python."
            .to_string()
    })
}

/// Whether the webview may load `target`: the shell's own page (the `tauri` scheme, or
/// `tauri.localhost` where the platform serves it over http or https) until the interface's
/// address is known, then only the interface's origin (scheme, host and port). Everything
/// else, the network included, is refused.
pub fn may_load(target: &Url, interface: Option<&Url>) -> bool {
    match interface {
        None => is_own_page(target),
        Some(interface) => {
            target.scheme() == interface.scheme()
                && target.host_str() == interface.host_str()
                && target.port_or_known_default() == interface.port_or_known_default()
        }
    }
}

fn is_own_page(target: &Url) -> bool {
    match target.scheme() {
        "tauri" => target.host_str() == Some("localhost"),
        "http" | "https" => target.host_str() == Some("tauri.localhost"),
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strings(values: &[&str]) -> Vec<OsString> {
        values.iter().map(OsString::from).collect()
    }

    #[test]
    fn python_is_the_variable_when_set() {
        assert_eq!(
            python(Some("/opt/py/bin/python".into())),
            OsString::from("/opt/py/bin/python")
        );
    }

    #[test]
    fn python_falls_back_when_unset_or_empty() {
        let fallback = if cfg!(windows) { "python" } else { "python3" };
        assert_eq!(python(None), OsString::from(fallback));
        assert_eq!(python(Some(OsString::new())), OsString::from(fallback));
    }

    #[test]
    fn passed_options_keeps_only_the_launcher_options() {
        let arguments = strings(&[
            "--config-dir",
            "/c",
            "--automation",
            "--data-dir=/d",
            "--print-url",
            "--ui-dir",
            "/u",
            "--idle-minutes",
            "5",
            "stray",
        ]);
        assert_eq!(
            passed_options(&arguments),
            strings(&[
                "--config-dir",
                "/c",
                "--data-dir=/d",
                "--ui-dir",
                "/u",
                "--idle-minutes",
                "5"
            ])
        );
    }

    #[test]
    fn passed_options_drops_an_option_without_its_value() {
        assert!(passed_options(&strings(&["--config-dir"])).is_empty());
    }

    #[test]
    fn launcher_arguments_end_with_print_url() {
        assert_eq!(
            launcher_arguments(&strings(&["--config-dir", "/c"])),
            strings(&["-m", "ithax.launcher", "--config-dir", "/c", "--print-url"])
        );
    }

    #[test]
    fn interface_url_takes_the_launcher_line() {
        let url = interface_url("http://127.0.0.1:41234/v1/ui/#token=abc\n").unwrap();
        assert_eq!(url.port(), Some(41234));
        assert_eq!(url.fragment(), Some("token=abc"));
        assert!(interface_url("noise\nhttp://127.0.0.1:5/v1/ui/#token=t\n\n").is_some());
    }

    #[test]
    fn interface_url_refuses_anything_else() {
        for output in [
            "",
            "not a url",
            "https://127.0.0.1:5/v1/ui/#token=t",
            "http://localhost:5/v1/ui/#token=t",
            "http://example.com:5/v1/ui/#token=t",
            "http://127.0.0.1/v1/ui/#token=t",
            "http://127.0.0.1:5/v1/other/#token=t",
            "http://127.0.0.1:5/v1/ui/?x=1#token=t",
            "http://127.0.0.1:5/v1/ui/",
            "http://127.0.0.1:5/v1/ui/#token=",
        ] {
            assert!(interface_url(output).is_none(), "{output}");
        }
    }

    #[test]
    fn run_reports_a_python_that_cannot_be_run() {
        let error = run(OsStr::new("/nonexistent/python"), &[]).unwrap_err();
        assert!(
            error.starts_with("/nonexistent/python could not be run"),
            "{error}"
        );
        assert!(error.contains(PYTHON_VARIABLE), "{error}");
    }

    #[cfg(unix)]
    #[test]
    fn run_reports_what_a_failing_launcher_said() {
        // `sh -m ithax.launcher --print-url` finds no script file `ithax.launcher`, says so
        // on its standard error and exits with a status that is not 0.
        let error = run(OsStr::new("sh"), &[]).unwrap_err();
        assert!(error.contains("ithax.launcher"), "{error}");
    }

    #[cfg(unix)]
    #[test]
    fn run_names_the_status_when_the_launcher_said_nothing() {
        // `false` ignores its arguments and exits with status 1, saying nothing.
        let error = run(OsStr::new("false"), &[]).unwrap_err();
        assert_eq!(error, "The launcher stopped (exit status: 1).");
    }

    #[cfg(unix)]
    #[test]
    fn run_refuses_output_that_is_not_the_address() {
        // `true` exits with status 0 and prints nothing.
        let error = run(OsStr::new("true"), &[]).unwrap_err();
        assert!(error.starts_with("The launcher did not print"), "{error}");
    }

    #[test]
    fn may_load_only_the_own_page_before_the_interface_is_known() {
        for allowed in [
            "tauri://localhost/index.html",
            "http://tauri.localhost/index.html",
        ] {
            assert!(may_load(&Url::parse(allowed).unwrap(), None), "{allowed}");
        }
        for refused in [
            "http://127.0.0.1:5/v1/ui/",
            "https://example.com/",
            "file:///etc/passwd",
            "tauri://elsewhere/",
            "data:text/html,hi",
        ] {
            assert!(!may_load(&Url::parse(refused).unwrap(), None), "{refused}");
        }
    }

    #[test]
    fn may_load_only_the_interface_origin_once_known() {
        let interface = Url::parse("http://127.0.0.1:41234/v1/ui/#token=t").unwrap();
        assert!(may_load(
            &Url::parse("http://127.0.0.1:41234/v1/ui/").unwrap(),
            Some(&interface)
        ));
        assert!(may_load(
            &Url::parse("http://127.0.0.1:41234/v1/ui/assets/x.js").unwrap(),
            Some(&interface)
        ));
        for refused in [
            "http://127.0.0.1:41235/v1/ui/",
            "https://127.0.0.1:41234/v1/ui/",
            "http://localhost:41234/v1/ui/",
            "https://github.com/Gravelaw/Ithax/issues/new",
            "tauri://localhost/index.html",
        ] {
            assert!(
                !may_load(&Url::parse(refused).unwrap(), Some(&interface)),
                "{refused}"
            );
        }
    }
}
