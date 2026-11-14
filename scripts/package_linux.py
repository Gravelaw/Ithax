"""Build the Linux package (spec 3 "Packaging"; AKS-127): ``python scripts/package_linux.py``.

It makes ``dist/ithax-<version>-linux-x86_64.tar.gz`` and its checksum file
``....tar.gz.sha256`` from this checkout (``docs/research/spec-3-linux-packaging.md``):

1. the interface (``npm ci`` and ``npm run build`` in ``ui/``) and the desktop shell
   (``npm ci`` and ``npm run build`` in ``desktop/``), from their lock files, unless
   ``--prebuilt`` says to take the ones already built;
2. the relocatable CPython of python-build-standalone, downloaded once into ``dist/cache``
   and checked against its pinned SHA-256;
3. the run-time wheels of ``packaging/linux/requirements.lock`` (exact versions and hashes)
   and the ``ithax`` wheel built from this checkout, installed into that Python;
4. the licences checked against ``packaging/linux/licences.json``: the build fails on any
   installed distribution not recorded there with its version, or any licence term not
   recorded as compatible;
5. the interface and templates under ``python/share/ithax``, the shell in ``lib/``, the
   commands and install scripts of ``packaging/linux``, the licence texts;
6. one archive in a fixed order, with fixed owners and the commit's time on every file.

Only the standard library is used, so any Python 3.11 or later runs it. Downloads need the
network; the archive it makes needs none to install or run.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging" / "linux"
LOCK = PACKAGING / "requirements.lock"
BUILD_CONSTRAINTS = PACKAGING / "build-constraints.txt"
LICENCES = PACKAGING / "licences.json"

PYTHON_RELEASE = "20261020"
PYTHON_VERSION = "3.13.16"
PYTHON_ARCHIVE = (
    f"cpython-{PYTHON_VERSION}+{PYTHON_RELEASE}"
    "-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
)
PYTHON_URL = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    f"{PYTHON_RELEASE}/{PYTHON_ARCHIVE.replace('+', '%2B')}"
)
PYTHON_SHA256 = "f326b7a386bf22def82e55dc3b95d2bef8b7c938b4c98ec32dd65433e7720b50"

#: Extension modules removed from the bundled Python: ``_dbm`` links Berkeley DB under the
#: Sleepycat licence and nothing in the package uses it (``licences.json``).
REMOVED_MODULES = ("_dbm",)

COMMANDS = ("ithax", "ithax-launcher", "ithax-mcp")

_PIN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s=]+)"
    r" --hash=sha256:(?P<sha256>[0-9a-f]{64})$"
)


class BuildError(Exception):
    """A step of the build that cannot go on; its message says why."""


@dataclass(frozen=True)
class Pin:
    """One line of ``requirements.lock``."""

    name: str
    version: str
    sha256: str


def normalise(name: str) -> str:
    """A distribution name as PEP 503 compares them."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(text: str) -> list[Pin]:
    """The pins of a lock file: each line that is not blank or a comment must be
    ``name==version --hash=sha256:<64 hex digits>``, each name once."""
    pins: list[Pin] = []
    seen: set[str] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        match = _PIN.fullmatch(line)
        if match is None:
            raise BuildError(f"requirements.lock line {number} is not pinned with a hash: {line}")
        name = normalise(match["name"])
        if name in seen:
            raise BuildError(f"requirements.lock names {match['name']} twice")
        seen.add(name)
        pins.append(Pin(match["name"], match["version"], match["sha256"]))
    return pins


def licence_terms(expression: str) -> list[str]:
    """The terms of an SPDX expression joined by ``AND`` and ``OR``, with any ``WITH``
    exception kept with its licence; parentheses are ignored."""
    flat = expression.replace("(", " ").replace(")", " ")
    return [term.strip() for term in re.split(r"\s+(?:AND|OR)\s+", flat) if term.strip()]


def check_licences(installed: Mapping[str, str], record: Mapping[str, Any]) -> list[str]:
    """Every problem with the licences: an installed distribution (name to version) that
    ``record["distributions"]`` does not list at that version, a listed one that is not
    installed, and any licence term, of a distribution, of what it bundles or of the
    Python, that ``record["compatible"]`` does not list."""
    compatible = set(record["compatible"])
    recorded = {normalise(name): (name, entry) for name, entry in record["distributions"].items()}
    found = {normalise(name): (name, version) for name, version in installed.items()}
    problems: list[str] = []
    for key, (name, version) in sorted(found.items()):
        if key not in recorded:
            problems.append(f"{name} {version} is installed but not in licences.json")
        elif recorded[key][1]["version"] != version:
            problems.append(
                f"{name} is installed at {version}; licences.json records "
                f"{recorded[key][1]['version']}"
            )
    for key, (name, _) in sorted(recorded.items()):
        if key not in found:
            problems.append(f"{name} is in licences.json but not installed")
    expressions: list[tuple[str, str]] = [("Python", record["python"]["licence"])]
    expressions += [
        (f"Python's {item['name']}", item["licence"]) for item in record["python"]["bundled"]
    ]
    for name, entry in record["distributions"].items():
        expressions.append((name, entry["licence"]))
        for bundled in entry.get("bundled", []):
            expressions.append((f"{name}'s bundled code", bundled.split(": ", 1)[-1]))
    for name, expression in expressions:
        for term in licence_terms(expression):
            if term not in compatible:
                problems.append(f"{name}: the licence term '{term}' is not recorded as compatible")
    return problems


def relocatable_script(text: str, python_bin: Path) -> str | None:
    """The script ``text`` made to run from wherever the package is unpacked, when it
    names the interpreter in ``python_bin`` by its absolute path, as pip writes console
    scripts: a first line ``#!<python_bin>/python3``, or, when that path is long, pip's
    three-line ``/bin/sh`` stub whose ``exec`` names ``<python_bin>/python3``. Either
    becomes a ``/bin/sh`` stub that runs the Python beside the script, as
    python-build-standalone's own scripts do. ``None`` otherwise."""
    folder = re.escape(str(python_bin))
    lines = text.split("\n")
    shebang = re.fullmatch("#!" + folder + "/(python[0-9.]*)", lines[0])
    pip_stub = re.compile("'''exec' ('?)" + folder + '/(python[0-9.]*)\\1 "\\$0" "\\$@"')
    if shebang is not None:
        interpreter, rest = shebang[1], lines[1:]
    elif (
        len(lines) > 2
        and lines[0] == "#!/bin/sh"
        and (exec_line := pip_stub.fullmatch(lines[1])) is not None
        and lines[2] == "' '''"
    ):
        interpreter, rest = exec_line[2], lines[3:]
    else:
        return None
    stub = [
        "#!/bin/sh",
        f'\'\'\'exec\' "$(dirname -- "$(realpath -- "$0")")"/\'{interpreter}\' "$0" "$@"',
        "' '''",
    ]
    return "\n".join(stub + rest) if rest else "\n".join(stub) + "\n"


def make_scripts_relocatable(python_bin: Path) -> list[Path]:
    """Rewrite the console scripts in ``python_bin`` that name it by absolute path; the
    scripts rewritten."""
    rewritten = []
    for path in sorted(python_bin.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = relocatable_script(text, python_bin)
        if new is not None:
            path.write_text(new, encoding="utf-8")
            rewritten.append(path)
    return rewritten


def record_hash(data: bytes) -> str:
    """A file's hash as a wheel's ``RECORD`` writes it."""
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"sha256={digest}"


def refresh_records(site_packages: Path, changed: Sequence[Path], removed: Sequence[Path]) -> None:
    """Bring every ``RECORD`` in ``site_packages`` in line with the files the build
    changed (new hash and size) or removed (line dropped), so the installed metadata is
    true and the same in every build."""
    changed_set = {path.resolve() for path in changed}
    removed_set = {path.resolve() for path in removed}
    for record in sorted(site_packages.glob("*.dist-info/RECORD")):
        lines = []
        for line in record.read_text(encoding="utf-8").splitlines():
            name = line.rsplit(",", 2)[0]
            target = (site_packages / name).resolve()
            if target in removed_set:
                continue
            if target in changed_set:
                data = target.read_bytes()
                line = f"{name},{record_hash(data)},{len(data)}"
            lines.append(line)
        record.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _reset(info: tarfile.TarInfo, mtime: int) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = mtime
    if info.isdir() or info.mode & stat.S_IXUSR:
        info.mode = 0o755
    else:
        info.mode = 0o644
    return info


def write_archive(folder: Path, archive: Path, mtime: int) -> None:
    """``folder`` as a gzip-compressed tar archive whose one top folder is
    ``folder.name``: members in name order, owned by 0, with ``mtime`` as every time,
    modes 0755 (folders and executables) or 0644, symbolic links kept, and no name or time
    in the gzip header, so the same files give the same bytes."""
    paths = sorted(folder.rglob("*"), key=lambda path: path.relative_to(folder).parts)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in [folder, *paths]:
                    name = Path(folder.name, path.relative_to(folder)).as_posix()
                    info = _reset(tar.gettarinfo(str(path), arcname=name), mtime)
                    if info.isreg():
                        with path.open("rb") as handle:
                            tar.addfile(info, handle)
                    else:
                        tar.addfile(info)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_checksum(archive: Path) -> Path:
    """``<archive>.sha256`` beside it, in the format ``sha256sum -c`` reads."""
    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(f"{sha256_file(archive)}  {archive.name}\n", encoding="ascii")
    return checksum


def third_party_text(record: Mapping[str, Any], crates: Sequence[Mapping[str, str]]) -> str:
    """``THIRD-PARTY-LICENSES.txt``: every bundled component with its version and
    licence, and where its licence text is."""
    python = record["python"]
    lines = [
        "Ithax is free software under the GNU Affero General Public License version 3 only",
        "(LICENSE). Its source is at https://github.com/Gravelaw/Ithax. It bundles the",
        "components below, each under its own licence.",
        "",
        f"Python: {python['name']} {python['version']}, {python['licence']}",
        f"  from {python['source']}.",
        "  Its licence: python/lib/python3.13/LICENSE.txt; the libraries built into it:",
    ]
    for item in python["bundled"]:
        version = f" {item['version']}" if item.get("version") else ""
        lines.append(f"  - {item['name']}{version}: {item['licence']}")
    lines += [
        "  Their licence texts: python/licenses/.",
        f"  Removed: {python['removed']}.",
        "",
        "Python packages installed into it (licence texts in each one's .dist-info folder",
        "under python/lib/python3.13/site-packages):",
    ]
    for name, entry in sorted(record["distributions"].items(), key=lambda item: item[0].lower()):
        lines.append(f"  - {name} {entry['version']}: {entry['licence']}")
        lines += [f"      bundles {bundled}" for bundled in entry.get("bundled", [])]
    lines += [
        "",
        "The interface (python/share/ithax/ui): its npm packages and their licences are in",
        "python/share/ithax/ui/THIRD-PARTY-NOTICES.txt.",
        "",
        "The desktop shell (lib/ithax-desktop) is built from these Rust crates:",
    ]
    lines += [f"  - {crate['name']} {crate['version']}: {crate['license']}" for crate in crates]
    lines += [
        "  It loads the system's WebKitGTK, GTK and libsoup (LGPL), which are not bundled.",
        "",
    ]
    return "\n".join(lines)


def shipped_crates(metadata: Mapping[str, Any], root_name: str) -> list[dict[str, str]]:
    """The crates the program ``root_name`` is built from, from ``cargo metadata``: those
    reached from it through normal dependencies (not build or development ones), in name
    order, with their version and licence."""
    packages = {package["id"]: package for package in metadata["packages"]}
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    start = next(pid for pid, package in packages.items() if package["name"] == root_name)
    reached = {start}
    stack = [start]
    while stack:
        for dep in nodes[stack.pop()]["deps"]:
            normal = any(kind["kind"] is None for kind in dep["dep_kinds"])
            if normal and dep["pkg"] not in reached:
                reached.add(dep["pkg"])
                stack.append(dep["pkg"])
    reached.discard(start)
    crates = [
        {
            "name": packages[pid]["name"],
            "version": packages[pid]["version"],
            "license": packages[pid].get("license") or "see the crate",
        }
        for pid in reached
    ]
    return sorted(crates, key=lambda crate: (crate["name"], crate["version"]))


def set_times(folder: Path, mtime: int) -> None:
    """Every file, link and folder under ``folder`` gets ``mtime``, so the bytecode
    compiled next matches the times the archive will carry."""
    for path in [*folder.rglob("*"), folder]:
        os.utime(path, (mtime, mtime), follow_symlinks=False)


# The steps below run programs and need the network; the package test (marker
# ``package``) exercises them by building the package.


def _run(
    command: Sequence[str | Path], cwd: Path = ROOT, env: Mapping[str, str] | None = None
) -> None:
    print("+", " ".join(str(part) for part in command), flush=True)
    done = subprocess.run([str(part) for part in command], cwd=cwd, env=env, check=False)
    if done.returncode != 0:
        raise BuildError(f"{command[0]} failed with status {done.returncode}")


def _output(command: Sequence[str | Path], cwd: Path = ROOT) -> str:
    return subprocess.run(
        [str(part) for part in command], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def fetch_python(cache: Path) -> Path:
    """The pinned Python archive, downloaded into ``cache`` when not there, its SHA-256
    checked either way."""
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / PYTHON_ARCHIVE
    if not archive.exists():
        print(f"Downloading {PYTHON_URL}", flush=True)
        partial = archive.with_name(archive.name + ".part")
        with urllib.request.urlopen(PYTHON_URL, timeout=300) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(archive)
    if sha256_file(archive) != PYTHON_SHA256:
        raise BuildError(f"{archive} does not have the pinned SHA-256 {PYTHON_SHA256}")
    return archive


def installed_distributions(python: Path) -> dict[str, str]:
    script = (
        "import importlib.metadata as m, json; "
        "print(json.dumps({d.metadata['Name']: d.version for d in m.distributions()}))"
    )
    found: dict[str, str] = json.loads(_output([python, "-I", "-c", script]))
    return found


def build(out: Path, prebuilt: bool) -> Path:
    """Build the package into ``out``; the archive's path."""
    sys.path.insert(0, str(ROOT / "src"))
    import ithax  # the checkout's own version

    version = ithax.__version__
    name = f"ithax-{version}-linux-x86_64"
    commit = _output(["git", "rev-parse", "HEAD"]).strip()
    mtime = int(
        os.environ.get("SOURCE_DATE_EPOCH") or _output(["git", "log", "-1", "--format=%ct"])
    )
    record = json.loads(LICENCES.read_text(encoding="utf-8"))
    pins = read_lock(LOCK.read_text(encoding="utf-8"))

    ui_dist = ROOT / "ui" / "dist"
    shell = ROOT / "desktop" / "src-tauri" / "target" / "release" / "ithax-desktop"
    if not prebuilt:
        _run(["npm", "ci"], cwd=ROOT / "ui")
        _run(["npm", "run", "build"], cwd=ROOT / "ui")
        _run(["npm", "ci"], cwd=ROOT / "desktop")
        _run(["npm", "run", "build"], cwd=ROOT / "desktop")
    for needed in (ui_dist / "index.html", shell):
        if not needed.is_file():
            raise BuildError(f"{needed} is missing; build it or leave out --prebuilt")

    out.mkdir(parents=True, exist_ok=True)
    python_archive = fetch_python(out / "cache")
    with tempfile.TemporaryDirectory(dir=out) as scratch:
        stage = Path(scratch) / name
        stage.mkdir()
        with tarfile.open(python_archive) as tar:
            tar.extractall(stage, filter="tar")
        python = stage / "python" / "bin" / "python3"
        for module in REMOVED_MODULES:
            for path in (stage / "python" / "lib" / "python3.13" / "lib-dynload").glob(
                f"{module}.*.so"
            ):
                path.unlink()

        wheels = Path(scratch) / "wheels"
        constraint_env = {**os.environ, "PIP_CONSTRAINT": str(BUILD_CONSTRAINTS)}
        _run(
            [python, "-I", "-m", "pip", "wheel", "--no-deps", "-w", wheels, ROOT],
            env=constraint_env,
        )
        install: list[str | Path] = [python, "-I", "-m", "pip", "install", "--no-deps"]
        install += ["--disable-pip-version-check", "--root-user-action=ignore", "--no-compile"]
        _run([*install, "--only-binary=:all:", "--require-hashes", "-r", LOCK])
        _run([*install, *sorted(wheels.glob("ithax-*.whl"))])

        installed = installed_distributions(python)
        installed.pop("ithax", None)
        problems = check_licences(installed, record)
        locked = {normalise(pin.name): pin.version for pin in pins}
        for dist, dist_version in installed.items():
            if dist != "pip" and locked.get(normalise(dist)) != dist_version:
                problems.append(f"{dist} {dist_version} is installed but not pinned in the lock")
        if problems:
            raise BuildError("licence or pin problems:\n  " + "\n  ".join(problems))
        rewritten = make_scripts_relocatable(stage / "python" / "bin")
        print(f"Made {len(rewritten)} console scripts relocatable", flush=True)
        # pip records the ithax wheel's temporary path; the package keeps no build path.
        site_packages = stage / "python" / "lib" / "python3.13" / "site-packages"
        direct_urls = sorted(site_packages.glob("ithax-*.dist-info/direct_url.json"))
        for path in direct_urls:
            path.unlink()
        refresh_records(site_packages, rewritten, direct_urls)

        share = stage / "python" / "share" / "ithax"
        shutil.copytree(ui_dist, share / "ui")
        shutil.copytree(
            ROOT / "templates", share / "templates", ignore=shutil.ignore_patterns("__pycache__")
        )
        shutil.copytree(PACKAGING / "python-licences", stage / "python" / "licenses")
        (stage / "lib").mkdir()
        shutil.copy2(shell, stage / "lib" / "ithax-desktop")
        (stage / "bin").mkdir()
        for command in COMMANDS:
            shutil.copy2(PACKAGING / "bin" / command, stage / "bin" / command)
        for script in ("install.sh", "uninstall.sh"):
            shutil.copy2(PACKAGING / script, stage / script)
        for executable in [
            *(stage / "bin").iterdir(),
            stage / "install.sh",
            stage / "uninstall.sh",
        ]:
            executable.chmod(0o755)
        (stage / "share").mkdir()
        shutil.copy2(
            ROOT / "desktop" / "src-tauri" / "icons" / "128x128.png", stage / "share" / "ithax.png"
        )
        shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
        shutil.copy2(PACKAGING / "INSTALL.txt", stage / "INSTALL.txt")
        crates = shipped_crates(
            json.loads(
                _output(
                    [
                        "cargo",
                        "metadata",
                        "--format-version",
                        "1",
                        "--locked",
                        "--filter-platform",
                        "x86_64-unknown-linux-gnu",
                    ],
                    cwd=ROOT / "desktop" / "src-tauri",
                )
            ),
            "ithax-desktop",
        )
        (stage / "THIRD-PARTY-LICENSES.txt").write_text(third_party_text(record, crates), "utf-8")
        info = {
            "name": name,
            "version": version,
            "commit": commit,
            "python": {"archive": PYTHON_ARCHIVE, "sha256": PYTHON_SHA256},
            "lock": sha256_file(LOCK),
            "distributions": dict(sorted(installed.items(), key=lambda item: item[0].lower())),
        }
        (stage / "BUILD-INFO.json").write_text(json.dumps(info, indent=2) + "\n", "utf-8")

        set_times(stage, mtime)
        # One process and a fixed hash seed, so the bytecode is the same in every build
        # (in a pool, what a worker compiled before changed a file's bytes); -s and -P
        # isolate it as -I would, which would also ignore the seed.
        hash_seed = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        hash_seed["PYTHONHASHSEED"] = "0"
        _run(
            [
                python,
                "-s",
                "-P",
                "-m",
                "compileall",
                "-f",
                "-q",
                "--invalidation-mode",
                "timestamp",
                # Paths in the bytecode start at the package's folder, not the build's
                # (Python sets the real path when it loads them).
                "-s",
                stage,
                "-p",
                name,
                stage / "python" / "lib" / "python3.13",
            ],
            env=hash_seed,
        )
        archive = out / f"{name}.tar.gz"
        write_archive(stage, archive, mtime)
    checksum = write_checksum(archive)
    print(f"Wrote {archive} ({archive.stat().st_size / 1e6:.0f} MB) and {checksum.name}")
    return archive


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Ithax Linux package.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="output folder (dist)")
    parser.add_argument(
        "--prebuilt",
        action="store_true",
        help="take ui/dist and the desktop shell as built, without npm",
    )
    arguments = parser.parse_args(argv)
    try:
        build(arguments.out.resolve(), arguments.prebuilt)
    except BuildError as error:
        print(f"package_linux: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
