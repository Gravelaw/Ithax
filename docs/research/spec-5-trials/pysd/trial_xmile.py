"""Spec 5 trial: PySD runs the system dynamics benchmarks from XMILE 1.0 files.

The XMILE files `sir.xmile` and `predator_prey.xmile` hold the same models as `sir.mdl`
and `predator_prey.mdl` (trial_pysd.py). Each pair is run at the same steps, and the
XMILE results are compared with the Vensim results and with the known answers.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 pysd && VIRTUAL_ENV=$PWD/pysd uv pip install pysd==3.14.3 scipy
Run (from this folder):
    <venv>/bin/python trial_xmile.py > output_xmile.txt

Known answers as in trial_pysd.py: SIR final size 797.154100 and peak 153.926660;
Lotka-Volterra V = delta x - gamma ln x + beta y - alpha ln y = -3.813315552, constant.
"""

import math
import pathlib
import shutil
import tempfile
import warnings

import numpy as np
import pysd
from scipy.optimize import brentq

HERE = pathlib.Path(__file__).resolve().parent
warnings.simplefilter("ignore")


def load(name: str, tmp: pathlib.Path):
    shutil.copy(HERE / name, tmp / name)  # PySD writes the translated .py beside the file
    if name.endswith(".xmile"):
        return pysd.read_xmile(str(tmp / name))
    return pysd.read_vensim(str(tmp / name))


def runs(stem: str, columns: list[str], steps: tuple[float, ...], tmp: pathlib.Path):
    """Yield (step, XMILE frame, Vensim frame), checking that each step was applied."""
    xmile, vensim = load(f"{stem}.xmile", tmp), load(f"{stem}.mdl", tmp)
    for dt in steps:
        pair = [m.run(time_step=dt, saveper=dt, return_columns=columns) for m in (xmile, vensim)]
        for out in pair:
            assert abs(out.index[1] - out.index[0] - dt) < 1e-12, "time step not applied"
        diff = max(
            float(np.max(np.abs(pair[0][c].to_numpy() - pair[1][c].to_numpy()))) for c in columns
        )
        yield dt, pair[0], diff


def sir(tmp: pathlib.Path) -> None:
    n, i0, r0 = 1000.0, 1.0, 2.0
    s0 = n - i0
    s_inf = brentq(lambda s: s - s0 * math.exp(-r0 * (n - s) / n), 1e-9, n / r0)
    final_size = n - s_inf
    peak = i0 + s0 - (n / r0) * (1 + math.log(r0 * s0 / n))
    print(f"SIR known: final size {final_size:.6f}, peak infected {peak:.6f}")
    columns = ["Susceptible", "Infected", "Recovered"]
    for dt, out, diff in runs("sir", columns, (0.25, 0.0625, 0.015625), tmp):
        r_end = out["Recovered"].iloc[-1] + out["Infected"].iloc[-1]
        print(
            f"  XMILE dt {dt}: final size {r_end:.6f} (error {r_end - final_size:+.4f}), "
            f"peak {out['Infected'].max():.6f} (error {out['Infected'].max() - peak:+.4f}); "
            f"largest difference from .mdl {diff:.1e}"
        )


def predator_prey(tmp: pathlib.Path) -> None:
    a, b, g, d = 1.0, 0.1, 1.5, 0.075

    def v(x, y):
        return d * x - g * np.log(x) + b * y - a * np.log(y)

    print(f"Lotka-Volterra known: V constant = {v(10.0, 5.0):.9f}")
    for dt, out, diff in runs("predator_prey", ["Prey", "Predators"], (0.01, 0.001, 0.0001), tmp):
        vv = v(out["Prey"].to_numpy(), out["Predators"].to_numpy())
        drift = np.max(np.abs(vv - vv[0])) / abs(vv[0])
        print(
            f"  XMILE dt {dt}: V(15) {vv[-1]:.9f}, max relative drift {drift:.2e}; "
            f"largest difference from .mdl {diff:.1e}"
        )


def main() -> None:
    print("pysd", pysd.__version__)
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        sir(tmp)
        predator_prey(tmp)


if __name__ == "__main__":
    main()
