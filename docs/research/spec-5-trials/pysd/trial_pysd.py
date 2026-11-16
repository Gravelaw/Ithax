"""Spec 5 trial: PySD runs two Vensim models with known answers.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 pysd && VIRTUAL_ENV=$PWD/pysd uv pip install pysd==3.14.3 scipy
Run (from this folder):
    <venv>/bin/python trial_pysd.py > output.txt

Known answers (computed here with scipy's root finder, not by simulation):
- SIR (sir.mdl; N = 1000, I0 = 1, beta = 0.5/day, gamma = 0.25/day, R0 = 2):
  final susceptible S_inf solves S_inf = S0 exp(-R0 (N - S_inf) / N), and the
  peak of Infected is I0 + S0 - (N / R0) (1 + ln(R0 S0 / N)), reached when S = N / R0.
- Lotka-Volterra (predator_prey.mdl; alpha 1, beta 0.1, gamma 1.5, delta 0.075,
  x0 = 10, y0 = 5): V = delta x - gamma ln x + beta y - alpha ln y is constant.
PySD integrates with a fixed time step (Euler), so each model is run at several steps.
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
    return pysd.read_vensim(str(tmp / name))


def sir(tmp: pathlib.Path) -> None:
    n, i0, r0 = 1000.0, 1.0, 2.0
    s0 = n - i0
    s_inf = brentq(lambda s: s - s0 * math.exp(-r0 * (n - s) / n), 1e-9, n / r0)
    final_size = n - s_inf
    peak = i0 + s0 - (n / r0) * (1 + math.log(r0 * s0 / n))
    print(f"SIR known: final size (R_inf) {final_size:.6f}, peak infected {peak:.6f}")
    model = load("sir.mdl", tmp)
    for dt in (0.25, 0.0625, 0.015625):
        out = model.run(
            time_step=dt, saveper=dt, return_columns=["Susceptible", "Infected", "Recovered"]
        )
        assert abs(out.index[1] - out.index[0] - dt) < 1e-12, "time step not applied"
        r_end = out["Recovered"].iloc[-1] + out["Infected"].iloc[-1]
        print(
            f"  dt {dt}: final size {r_end:.6f} (error {r_end - final_size:+.4f}), "
            f"peak {out['Infected'].max():.6f} (error {out['Infected'].max() - peak:+.4f}), "
            f"I(200) {out['Infected'].iloc[-1]:.2e}"
        )


def predator_prey(tmp: pathlib.Path) -> None:
    a, b, g, d = 1.0, 0.1, 1.5, 0.075

    def v(x, y):
        return d * x - g * np.log(x) + b * y - a * np.log(y)

    print(f"Lotka-Volterra known: V constant = {v(10.0, 5.0):.9f}")
    model = load("predator_prey.mdl", tmp)
    for dt in (0.01, 0.001, 0.0001):
        out = model.run(time_step=dt, saveper=dt, return_columns=["Prey", "Predators"])
        assert abs(out.index[1] - out.index[0] - dt) < 1e-12, "time step not applied"
        vv = v(out["Prey"].to_numpy(), out["Predators"].to_numpy())
        drift = np.max(np.abs(vv - vv[0])) / abs(vv[0])
        print(f"  dt {dt}: V(15) {vv[-1]:.9f}, max relative drift over 15 years {drift:.2e}")


def main() -> None:
    print("pysd", pysd.__version__)
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        sir(tmp)
        predator_prey(tmp)


if __name__ == "__main__":
    main()
