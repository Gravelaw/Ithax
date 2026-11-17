"""Spec 5 trial: run OpenModelica's mass-spring-damper FMUs with FMPy.

Run by the CI workflow `.github/workflows/spec5-trials.yml`, once on the machine that
built the FMUs and once in a container without OpenModelica:
    python run_fmu.py MSD_dynamic.fmu MSD_static.fmu

Known answer: m = 1 kg, c = 4 N/m, d = 0.4 N.s/m, x(0) = 1 m, v(0) = 0, so wn = 2 rad/s,
zeta = 0.1, x(t) = exp(-zeta wn t) (cos wd t + zeta wn / wd sin wd t); x(10 s) =
0.079116024 m (docs/research/spec-5-trials/benchmarks/output.txt). Pass rule proposed in
spec 5: within 1e-5 m over 10 s.
"""

import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import fmpy
import numpy as np
from fmpy import read_model_description


def exact(t: np.ndarray) -> np.ndarray:
    wn, zeta = 2.0, 0.1
    wd = wn * math.sqrt(1 - zeta**2)
    return np.exp(-zeta * wn * t) * (np.cos(wd * t) + zeta * wn / wd * np.sin(wd * t))


def describe(path: str) -> None:
    md = read_model_description(path, validate=True)
    print(
        f"{path}: FMI {md.fmiVersion}, tool {md.generationTool!r}, "
        f"co-simulation {md.coSimulation is not None}, "
        f"model exchange {md.modelExchange is not None}"
    )
    with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as tmp:
        # Every file under binaries/, not only names ending in .so: the CVODE FMU ships
        # libsundials_*.so.5 beside the model (CI run 43938942488 missed them).
        files = [n for n in z.namelist() if n.startswith("binaries/") and not n.endswith("/")]
        print(f"  binaries: {files}")
        z.extractall(tmp, members=files)  # together, so a RUNPATH of $ORIGIN resolves
        notices = [n for n in z.namelist() if re.search(r"licen[cs]e|copying|notice", n, re.I)]
        print(f"  licence or notice files in the FMU: {notices or 'none'}")
        for name in files:
            if ".so" not in name:
                continue
            ldd = subprocess.run(["ldd", f"{tmp}/{name}"], capture_output=True, text=True)
            print(
                f"  ldd {name}:\n    " + (ldd.stdout or ldd.stderr).strip().replace("\n", "\n    ")
            )


def run(path: str, step: float = 0.01) -> bool:
    try:
        res = fmpy.simulate_fmu(
            path, stop_time=10.0, output_interval=step, relative_tolerance=1e-8, output=["x", "v"]
        )
    except Exception as error:  # report, do not hide: the trial records what happened
        print(f"  simulate_fmu failed: {type(error).__name__}: {error}")
        return False
    t, x = res["time"], res["x"]
    err = float(np.max(np.abs(x - exact(t))))
    ok = err <= 1e-5
    print(
        f"  step {step:g} s: {len(t)} samples, x(10) = {x[-1]:.9f} m, exact {exact(t)[-1]:.9f} m, "
        f"max |error| {err:.2e} m, within 1e-5: {ok}"
    )
    return ok


def main() -> None:
    print("fmpy", fmpy.__version__, "numpy", np.__version__, "python", sys.version.split()[0])
    results = []
    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"{path}: not built")
            results.append(False)
            continue
        describe(path)
        results.append(run(path))
        # A tenfold smaller communication step: an error that falls about tenfold points to a
        # first-order method stepping at the communication interval (forward Euler).
        run(path, 0.001)
    print("all within 1e-5:", all(results))


if __name__ == "__main__":
    main()
