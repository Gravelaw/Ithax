"""``python -m ithax.install_check``: check that an installation can work (spec 3
"Packaging"; AKS-127, owner to confirm).

The Linux package's ``install.sh`` runs it with the bundled Python before it links any
command, so a package that is incomplete or does not run on the machine is reported at once.
It checks that the Phase 1 engines load (``ithax.engines`` entry points), that the built
interface's ``index.html`` is where the service will look for it, and that every template
package there can be served, the same loader the service uses. The interface and templates
folders are the service's defaults (``ithax.service.config``) unless ``--ui-dir`` and
``--templates-dir`` name others. The exit status is 0 when nothing is wrong, else 1, with
each problem on standard error. These are messages about the installation, not about a
model, so they are plain text, as the launcher's are.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

import ithax
from ithax.engines.adapter import EngineAdapter
from ithax.engines.registry import load_adapters
from ithax.service.config import default_templates_dir, default_ui_dir
from ithax.templates import load_package, package_folders

__all__ = ["PHASE_1_ENGINES", "Report", "check", "main"]

#: The adapters every Phase 1 installation holds (spec 2): HiGHS and SimPy.
PHASE_1_ENGINES = ("highs", "simpy")


@dataclass
class Report:
    """What ``check`` found: the engines that load, the number of templates that can be
    served, and each problem in words."""

    engines: list[str] = field(default_factory=list)
    templates: int = 0
    problems: list[str] = field(default_factory=list)


def check(
    ui_dir: Path, templates_dir: Path, adapters: Mapping[str, EngineAdapter] | None = None
) -> Report:
    """Check the engines (``adapters``, by default those installed), the interface in
    ``ui_dir`` and the template packages in ``templates_dir``."""
    loaded = load_adapters() if adapters is None else adapters
    report = Report(engines=sorted(loaded))
    for name in PHASE_1_ENGINES:
        if name not in loaded:
            report.problems.append(f"The engine '{name}' is not installed or does not load.")
    index = ui_dir / "index.html"
    if not index.is_file():
        report.problems.append(f"The interface is missing: {index}.")
    folders = package_folders(templates_dir)
    if not folders:
        report.problems.append(f"No template package was found in {templates_dir}.")
    for folder in folders:
        result = load_package(folder, adapters=loaded)
        if result.package is None:
            codes = ", ".join(sorted({issue.code for issue in result.issues}))
            report.problems.append(f"The template '{folder.name}' cannot be served: {codes}.")
        else:
            report.templates += 1
    return report


def main(
    argv: Sequence[str] | None = None, *, out: TextIO | None = None, err: TextIO | None = None
) -> int:
    """Run the check and report it; return the exit status."""
    parser = argparse.ArgumentParser(
        prog="python -m ithax.install_check",
        description="Check that the engines, the interface and the templates are installed.",
    )
    parser.add_argument("--ui-dir", type=Path, help="the built interface (default: the service's)")
    parser.add_argument(
        "--templates-dir", type=Path, help="the template packages (default: the service's)"
    )
    arguments = parser.parse_args(argv)
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    ui_dir = arguments.ui_dir or default_ui_dir()
    templates_dir = arguments.templates_dir or default_templates_dir()
    report = check(ui_dir, templates_dir)
    for problem in report.problems:
        print(problem, file=err)
    if report.problems:
        return 1
    python = ".".join(str(part) for part in sys.version_info[:3])
    print(
        f"Ithax {ithax.__version__} on Python {python}: engines {', '.join(report.engines)}; "
        f"the interface in {ui_dir}; {report.templates} templates in {templates_dir}.",
        file=out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
