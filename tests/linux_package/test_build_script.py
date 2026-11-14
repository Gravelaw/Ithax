"""The pure parts of the package build, ``scripts/package_linux.py`` (spec 3 "Packaging";
AKS-127), and the files it reads: the lock, the licence record and the commands. The build
itself runs under the marker ``package`` (``test_linux_package.py``)."""

import gzip
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tomllib
from pathlib import Path
from typing import Any

import pytest
from packaging.requirements import Requirement

from linux_package.build_script import ROOT, build

PACKAGING = ROOT / "packaging" / "linux"


def record() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((PACKAGING / "licences.json").read_text("utf-8"))
    return loaded


# The lock.

GOOD_HASH = "a" * 64


def test_a_lock_line_is_a_name_an_exact_version_and_a_hash() -> None:
    pins = build.read_lock(f"# comment\n\nNumPy==2.5.4 --hash=sha256:{GOOD_HASH}\n")
    assert pins == [build.Pin("NumPy", "2.5.4", GOOD_HASH)]


@pytest.mark.parametrize(
    "line",
    [
        "numpy>=2.5",
        "numpy==2.5.4",
        f"numpy==2.5.4 --hash=sha256:{'a' * 63}",
        f"numpy==2.5.4 --hash=md5:{GOOD_HASH}",
        f"numpy==2.5.4  --hash=sha256:{GOOD_HASH}",
    ],
)
def test_a_lock_line_without_an_exact_pin_and_hash_is_refused(line: str) -> None:
    with pytest.raises(build.BuildError, match="line 1 is not pinned with a hash"):
        build.read_lock(line)


def test_a_name_locked_twice_is_refused() -> None:
    text = f"a_b==1 --hash=sha256:{GOOD_HASH}\nA-B==2 --hash=sha256:{GOOD_HASH}\n"
    with pytest.raises(build.BuildError, match="names A-B twice"):
        build.read_lock(text)


def test_the_lock_pins_every_run_time_dependency_within_its_range() -> None:
    pins = {
        build.normalise(pin.name): pin
        for pin in build.read_lock((PACKAGING / "requirements.lock").read_text("utf-8"))
    }
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    for line in project["dependencies"]:
        requirement = Requirement(line)
        pin = pins[build.normalise(requirement.name)]
        assert requirement.specifier.contains(pin.version), (line, pin.version)


def test_the_lock_and_the_licence_record_name_the_same_distributions() -> None:
    locked = {
        build.normalise(pin.name): pin.version
        for pin in build.read_lock((PACKAGING / "requirements.lock").read_text("utf-8"))
    }
    recorded = {
        build.normalise(name): entry["version"] for name, entry in record()["distributions"].items()
    }
    # pip comes with the bundled Python, not from the lock.
    assert recorded.pop("pip") == "26.2.2"
    assert recorded == locked


def test_the_build_constraints_pin_exact_versions() -> None:
    lines = (PACKAGING / "build-constraints.txt").read_text("utf-8").splitlines()
    pins = [line for line in lines if line and not line.startswith("#")]
    assert pins and all("==" in line for line in pins)
    assert any(line.startswith("hatchling==") for line in pins)


# Licences.


def test_licence_terms_split_and_or_and_keep_with() -> None:
    assert build.licence_terms("(Apache-2.0 OR BSD-3-Clause) AND MIT") == [
        "Apache-2.0",
        "BSD-3-Clause",
        "MIT",
    ]
    assert build.licence_terms("GPL-3.0-or-later WITH GCC-exception-3.1") == [
        "GPL-3.0-or-later WITH GCC-exception-3.1"
    ]


def test_the_recorded_licences_are_all_compatible() -> None:
    document = record()
    installed = {name: entry["version"] for name, entry in document["distributions"].items()}
    assert build.check_licences(installed, document) == []


def test_an_unrecorded_or_changed_distribution_is_a_problem() -> None:
    document = record()
    installed = {name: entry["version"] for name, entry in document["distributions"].items()}
    installed["numpy"] = "9.9"
    installed["leftpad"] = "1.0"
    del installed["simpy"]
    assert build.check_licences(installed, document) == [
        "leftpad 1.0 is installed but not in licences.json",
        "numpy is installed at 9.9; licences.json records 2.5.4",
        "simpy is in licences.json but not installed",
    ]


def test_an_incompatible_licence_term_is_a_problem() -> None:
    document = record()
    document["distributions"]["simpy"]["licence"] = "MIT OR SSPL-1.0"
    document["distributions"]["numpy"]["bundled"].append("thing: BUSL-1.1")
    document["python"]["bundled"].append({"name": "x", "licence": "CC-BY-NC-4.0"})
    installed = {name: entry["version"] for name, entry in document["distributions"].items()}
    assert build.check_licences(installed, document) == [
        "Python's x: the licence term 'CC-BY-NC-4.0' is not recorded as compatible",
        "numpy's bundled code: the licence term 'BUSL-1.1' is not recorded as compatible",
        "simpy: the licence term 'SSPL-1.0' is not recorded as compatible",
    ]


def test_no_gpl_only_or_non_free_term_is_recorded_as_compatible() -> None:
    compatible = set(record()["compatible"])
    assert not {term for term in compatible if term.startswith(("GPL-2.0", "SSPL", "BUSL"))}
    assert not {term for term in compatible if "NC" in term.split("-")}


def test_every_python_licence_text_is_shipped() -> None:
    texts = {path.name for path in (PACKAGING / "python-licences").iterdir()}
    assert "LICENSE.cpython.txt" in texts
    assert "LICENSE.openssl-3.txt" in texts
    assert "LICENSE.bdb.txt" not in texts  # _dbm is removed (REMOVED_MODULES)
    assert build.REMOVED_MODULES == ("_dbm",)


# Console scripts.


def test_a_script_naming_the_build_python_becomes_a_relative_stub(tmp_path: Path) -> None:
    python_bin = tmp_path / "stage" / "python" / "bin"
    text = f"#!{python_bin}/python3.13\nimport sys\nprint(sys.argv)\n"
    new = build.relocatable_script(text, python_bin)
    assert new is not None
    assert new.startswith("#!/bin/sh\n'''exec' ")
    assert '\'python3.13\' "$0" "$@"' in new
    assert new.endswith("import sys\nprint(sys.argv)\n")
    assert str(tmp_path) not in new


def test_other_scripts_are_left_alone(tmp_path: Path) -> None:
    python_bin = tmp_path / "bin"
    assert build.relocatable_script("#!/bin/sh\necho hi\n", python_bin) is None
    assert build.relocatable_script(f"#!{python_bin}/python3 -E\nx\n", python_bin) is None
    assert build.relocatable_script(f"#!{python_bin}/python3", python_bin) is not None


def test_pips_sh_stub_for_a_long_path_becomes_the_relative_stub(tmp_path: Path) -> None:
    python_bin = tmp_path / "a long folder" / "bin"
    relative = '\'\'\'exec\' "$(dirname -- "$(realpath -- "$0")")"/\'python3\' "$0" "$@"'
    for quote in ("", "'"):
        exec_line = f"'''exec' {quote}{python_bin}/python3{quote} \"$0\" \"$@\""
        text = f"#!/bin/sh\n{exec_line}\n' '''\nimport sys\n"
        new = build.relocatable_script(text, python_bin)
        assert new is not None
        assert new == f"#!/bin/sh\n{relative}\n' '''\nimport sys\n"
        assert str(tmp_path) not in new
    other = "#!/bin/sh\n'''exec' /elsewhere/python3 \"$0\" \"$@\"\n' '''\nx\n"
    assert build.relocatable_script(other, python_bin) is None
    assert build.relocatable_script("#!/bin/sh\n", python_bin) is None


def test_records_follow_the_files_the_build_changed_or_removed(tmp_path: Path) -> None:
    site = tmp_path / "lib" / "python3.13" / "site-packages"
    info = site / "x-1.dist-info"
    info.mkdir(parents=True)
    script = tmp_path / "bin" / "x"
    script.parent.mkdir()
    script.write_bytes(b"new body")
    (info / "direct_url.json").write_text("{}")
    (info / "RECORD").write_text(
        "x/__init__.py,sha256=abc,3\n"
        "../../../bin/x,sha256=old,99\n"
        "x-1.dist-info/direct_url.json,sha256=def,2\n"
        "x-1.dist-info/RECORD,,\n"
    )
    build.refresh_records(site, [script], [info / "direct_url.json"])
    assert (info / "RECORD").read_text() == (
        "x/__init__.py,sha256=abc,3\n"
        f"../../../bin/x,{build.record_hash(b'new body')},8\n"
        "x-1.dist-info/RECORD,,\n"
    )
    assert build.record_hash(b"") == "sha256=47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU"


def test_a_rewritten_script_runs_after_its_folder_moves(tmp_path: Path) -> None:
    # A stand-in "python" that prints its arguments, and a script made for that folder.
    first = tmp_path / "first" / "bin"
    first.mkdir(parents=True)
    fake = first / "python3"
    fake.write_text('#!/bin/sh\necho "ran $1"\n')
    fake.chmod(0o755)
    script = first / "tool"
    script.write_text(f"#!{first}/python3\nbody\n")
    script.chmod(0o755)
    (first / "data").write_bytes(b"\xff\xfe")  # not text: skipped
    os.symlink("python3", first / "python")  # a link: skipped
    assert build.make_scripts_relocatable(first) == [script]
    moved = tmp_path / "second"
    (tmp_path / "first").rename(moved)
    done = subprocess.run([moved / "bin" / "tool"], capture_output=True, text=True, check=True)
    assert done.stdout == f"ran {moved / 'bin' / 'tool'}\n"


# The archive and its checksum.


def make_tree(root: Path) -> Path:
    folder = root / "pkg-1"
    (folder / "bin").mkdir(parents=True)
    (folder / "bin" / "run").write_text("#!/bin/sh\n")
    (folder / "bin" / "run").chmod(0o700)
    (folder / "data.txt").write_text("data")
    (folder / "data.txt").chmod(0o600)
    os.symlink("data.txt", folder / "link")
    return folder


def test_the_archive_is_the_same_bytes_for_the_same_files(tmp_path: Path) -> None:
    first = make_tree(tmp_path / "a")
    second = make_tree(tmp_path / "b")
    os.utime(second / "data.txt", (1, 1))
    build.write_archive(first, tmp_path / "a.tar.gz", 1_700_000_000)
    build.write_archive(second, tmp_path / "b.tar.gz", 1_700_000_000)
    assert (tmp_path / "a.tar.gz").read_bytes() == (tmp_path / "b.tar.gz").read_bytes()


def test_the_archive_has_one_folder_fixed_owners_times_and_modes(tmp_path: Path) -> None:
    folder = make_tree(tmp_path)
    archive = tmp_path / "out.tar.gz"
    build.write_archive(folder, archive, 1_700_000_000)
    raw = archive.read_bytes()
    assert raw[4:8] == b"\0\0\0\0"  # no time in the gzip header
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw))) as tar:
        members = {member.name: member for member in tar.getmembers()}
    assert list(members) == ["pkg-1", "pkg-1/bin", "pkg-1/bin/run", "pkg-1/data.txt", "pkg-1/link"]
    assert {(m.uid, m.gid, m.uname, m.gname, m.mtime) for m in members.values()} == {
        (0, 0, "", "", 1_700_000_000)
    }
    assert members["pkg-1/bin/run"].mode == 0o755
    assert members["pkg-1/data.txt"].mode == 0o644
    assert members["pkg-1"].mode == 0o755
    assert members["pkg-1/link"].issym() and members["pkg-1/link"].linkname == "data.txt"


def test_the_checksum_file_is_what_sha256sum_checks(tmp_path: Path) -> None:
    archive = tmp_path / "x.tar.gz"
    archive.write_bytes(b"package")
    checksum = build.write_checksum(archive)
    assert checksum.name == "x.tar.gz.sha256"
    digest = hashlib.sha256(b"package").hexdigest()
    assert checksum.read_text("ascii") == f"{digest}  x.tar.gz\n"
    assert build.sha256_file(archive) == digest
    done = subprocess.run(
        ["sha256sum", "-c", checksum.name], cwd=tmp_path, capture_output=True, text=True
    )
    assert done.returncode == 0 and done.stdout == "x.tar.gz: OK\n"


def test_set_times_reaches_every_file_and_link(tmp_path: Path) -> None:
    folder = make_tree(tmp_path)
    build.set_times(folder, 1_000_000)
    for path in [folder, *folder.rglob("*")]:
        assert os.lstat(path).st_mtime == 1_000_000


# Third-party notices.

METADATA = {
    "packages": [
        {"id": "app", "name": "ithax-desktop", "version": "0.0.0", "license": "AGPL-3.0-only"},
        {"id": "a", "name": "tauri", "version": "2.12.5", "license": "Apache-2.0 OR MIT"},
        {"id": "b", "name": "serde", "version": "1.0.0", "license": "MIT OR Apache-2.0"},
        {"id": "c", "name": "tauri-build", "version": "2.7.4", "license": "Apache-2.0 OR MIT"},
        {"id": "d", "name": "cc", "version": "1.2.0", "license": None},
        {"id": "e", "name": "unused", "version": "1.0.0", "license": "MIT"},
    ],
    "resolve": {
        "nodes": [
            {
                "id": "app",
                "deps": [
                    {"pkg": "a", "dep_kinds": [{"kind": None}]},
                    {"pkg": "c", "dep_kinds": [{"kind": "build"}]},
                ],
            },
            {
                "id": "a",
                "deps": [
                    {"pkg": "b", "dep_kinds": [{"kind": None}, {"kind": "build"}]},
                    {"pkg": "d", "dep_kinds": [{"kind": None}]},
                    {"pkg": "app", "dep_kinds": [{"kind": None}]},
                ],
            },
            {"id": "b", "deps": []},
            {"id": "c", "deps": [{"pkg": "e", "dep_kinds": [{"kind": None}]}]},
            {"id": "d", "deps": [{"pkg": "b", "dep_kinds": [{"kind": None}]}]},
            {"id": "e", "deps": []},
        ]
    },
}


def test_shipped_crates_follow_normal_dependencies_only() -> None:
    assert build.shipped_crates(METADATA, "ithax-desktop") == [
        {"name": "cc", "version": "1.2.0", "license": "see the crate"},
        {"name": "serde", "version": "1.0.0", "license": "MIT OR Apache-2.0"},
        {"name": "tauri", "version": "2.12.5", "license": "Apache-2.0 OR MIT"},
    ]


def test_the_notices_name_every_component_and_where_its_licence_is() -> None:
    document = record()
    crates = build.shipped_crates(METADATA, "ithax-desktop")
    text = build.third_party_text(document, crates)
    assert text.startswith("Ithax is free software under the GNU Affero General Public License")
    assert "Python: CPython 3.13.16, PSF-2.0" in text
    assert "  - OpenSSL 3.5.9: Apache-2.0" in text
    assert "  - libedit: BSD-3-Clause" in text
    assert "Their licence texts: python/licenses/." in text
    for name, entry in document["distributions"].items():
        assert f"  - {name} {entry['version']}: {entry['licence']}" in text
    assert "      bundles libgfortran: GPL-3.0-or-later WITH GCC-exception-3.1" in text
    assert "python/share/ithax/ui/THIRD-PARTY-NOTICES.txt" in text
    assert "  - tauri 2.12.5: Apache-2.0 OR MIT" in text
    assert text.endswith("not bundled.\n")


# The commands and install scripts that go into the package.


@pytest.mark.parametrize(
    "name",
    ["bin/ithax", "bin/ithax-launcher", "bin/ithax-mcp", "install.sh", "uninstall.sh"],
)
def test_the_package_scripts_are_executable_posix_shell(name: str) -> None:
    path = PACKAGING / name
    assert os.access(path, os.X_OK)
    assert path.read_text("utf-8").startswith("#!/bin/sh\n")
    assert subprocess.run(["sh", "-n", path], check=False).returncode == 0


@pytest.mark.parametrize("name", ["ithax", "ithax-launcher", "ithax-mcp"])
def test_each_command_isolates_the_bundled_python(name: str) -> None:
    text = (PACKAGING / "bin" / name).read_text("utf-8")
    assert "unset PYTHONHOME PYTHONPATH" in text
    assert "export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1" in text


def test_the_commands_are_the_ones_the_build_copies() -> None:
    assert sorted(path.name for path in (PACKAGING / "bin").iterdir()) == list(build.COMMANDS)


def test_the_pinned_python_is_named_in_the_licence_record() -> None:
    python = record()["python"]
    assert python["version"] == build.PYTHON_VERSION
    assert build.PYTHON_ARCHIVE in python["source"]
    assert build.PYTHON_URL.endswith(build.PYTHON_ARCHIVE.replace("+", "%2B"))
    assert len(build.PYTHON_SHA256) == 64
