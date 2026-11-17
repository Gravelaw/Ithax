"""Spec 5 trial: FMPy runs an FMI 2.0 Model Exchange FMU of a mass, spring and damper.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 fmpy && VIRTUAL_ENV=$PWD/fmpy uv pip install fmpy==0.3.32 numpy
Run (from this folder; needs gcc):
    <venv>/bin/python trial_msd.py > output.txt

The FMU only states the equations (msd.c); FMPy's CVODE integrates them. OpenModelica
could not be installed in the research container, so the FMU is hand-written in C
instead of exported from Modelica (docs/research/spec-5-openmodelica-fmu.md).
Known answer: m x'' + c x' + k x = 0, x(0) = 1, v(0) = 0, m = 1, c = 0.4, k = 4, so
wn = 2, zeta = 0.1, x(t) = exp(-zeta wn t) (cos wd t + zeta wn / wd sin wd t).
"""

import math
import pathlib
import subprocess
import tempfile
import zipfile

import fmpy
import numpy as np
from fmpy.validation import validate_fmu

HERE = pathlib.Path(__file__).resolve().parent
HEADERS = pathlib.Path(fmpy.__file__).parent / "c-code"


def build(workdir: pathlib.Path) -> pathlib.Path:
    lib = workdir / "msd.so"
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-O2", "-I", str(HEADERS), str(HERE / "msd.c"), "-o", str(lib)],
        check=True,
    )
    fmu = workdir / "msd.fmu"
    with zipfile.ZipFile(fmu, "w") as z:
        z.write(HERE / "modelDescription.xml", "modelDescription.xml")
        z.write(lib, "binaries/linux64/msd.so")
    return fmu


def analytic(t: np.ndarray, m: float, c: float, k: float) -> np.ndarray:
    wn = math.sqrt(k / m)
    zeta = c / (2 * math.sqrt(k * m))
    wd = wn * math.sqrt(1 - zeta**2)
    return np.exp(-zeta * wn * t) * (np.cos(wd * t) + zeta * wn / wd * np.sin(wd * t))


def main() -> None:
    print("fmpy", fmpy.__version__, "numpy", np.__version__)
    with tempfile.TemporaryDirectory() as tmp:
        fmu = build(pathlib.Path(tmp))
        print("validation problems:", validate_fmu(str(fmu)))
        for c in (0.4, 4.0):  # underdamped (zeta 0.1) and critically damped (zeta 1)
            res = fmpy.simulate_fmu(
                str(fmu),
                fmi_type="ModelExchange",
                solver="CVode",
                start_values={"c": c},
                stop_time=10.0,
                output_interval=0.01,
                relative_tolerance=1e-8,
                output=["x", "v"],
            )
            t = res["time"]
            if c < 4.0:
                exact = analytic(t, 1.0, c, 4.0)
            else:  # critically damped: x = (1 + wn t) exp(-wn t)
                exact = (1 + 2 * t) * np.exp(-2 * t)
            err = np.max(np.abs(res["x"] - exact))
            print(
                f"c={c}: {len(t)} samples, x(10)={res['x'][-1]:.9f}, "
                f"exact {exact[-1]:.9f}, max |error| {err:.2e}"
            )


if __name__ == "__main__":
    main()
