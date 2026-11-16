"""Spec 5 trial: SALib 1.6.0 Sobol and Morris on the Ishigami function, and
scipy.stats.qmc 1.18.1 Latin hypercube and Sobol samples for a designed experiment and an
uncertainty study.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 venv && VIRTUAL_ENV=$PWD/venv uv pip install salib==1.6.0 \
        scipy==1.18.1 numpy==2.5.5
Run (from this folder):
    <venv>/bin/python -W error trial_salib_qmc.py > output_salib_qmc.txt

Known answers (Ishigami, a = 7, b = 0.1, X_i independent uniform on [-pi, pi]):
the OpenTURNS use case "The Ishigami function" (openturns.github.io, source
use_case_ishigami.rst, read 2026-11-16) gives E[Y] = a/2,
Var Y = 1/2 + a^2/8 + b^2 pi^8/18 + b pi^4/5, V1 = (1 + b pi^4/5)^2 / 2, V2 = a^2/8,
V13 = b^2 pi^8 8/225, S_i = V_i / Var Y, S3 = 0, ST1 = (V1 + V13)/Var Y, ST2 = S2,
ST3 = V13/Var Y. The script evaluates these formulas; it does not take them from SALib.
"""

import importlib.metadata
import math

import numpy as np
import scipy
from SALib.analyze import morris as morris_analyze
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import morris as morris_sample
from SALib.sample import sobol as sobol_sample
from scipy.stats import qmc

A, B = 7.0, 0.1
PROBLEM = {"num_vars": 3, "names": ["x1", "x2", "x3"], "bounds": [[-math.pi, math.pi]] * 3}


def ishigami(x: np.ndarray) -> np.ndarray:
    return np.sin(x[:, 0]) + A * np.sin(x[:, 1]) ** 2 + B * x[:, 2] ** 4 * np.sin(x[:, 0])


def analytic() -> dict[str, float]:
    pi = math.pi
    var = 0.5 + A**2 / 8 + B**2 * pi**8 / 18 + B * pi**4 / 5
    v1, v2, v13 = 0.5 * (1 + B * pi**4 / 5) ** 2, A**2 / 8, B**2 * pi**8 * 8 / 225
    return {
        "mean": A / 2,
        "var": var,
        "S1": v1 / var,
        "S2": v2 / var,
        "S3": 0.0,
        "ST1": (v1 + v13) / var,
        "ST2": v2 / var,
        "ST3": v13 / var,
    }


def sobol(n: int, seed: int) -> dict[str, np.ndarray]:
    x = sobol_sample.sample(PROBLEM, n, calc_second_order=False, seed=seed)
    return dict(
        sobol_analyze.analyze(PROBLEM, ishigami(x), calc_second_order=False, seed=seed),
        evaluations=np.array([len(x)]),
    )


def main() -> None:
    print(
        f"salib={importlib.metadata.version('salib')} scipy={scipy.__version__} "
        f"numpy={np.__version__}"
    )
    known = analytic()
    print("analytic: " + " ".join(f"{k}={v:.4f}" for k, v in known.items()))
    for n in (2**10, 2**13):
        r = sobol(n, seed=11)
        print(f"[SALib sobol N={n}] evaluations={r['evaluations'][0]}")
        for i in range(3):
            print(
                f"  x{i + 1}: S1={r['S1'][i]:.4f} (known {known[f'S{i + 1}']:.4f}, "
                f"conf {r['S1_conf'][i]:.4f}) ST={r['ST'][i]:.4f} "
                f"(known {known[f'ST{i + 1}']:.4f}, conf {r['ST_conf'][i]:.4f})"
            )
    a, b = sobol(2**10, seed=11), sobol(2**10, seed=11)
    print(
        f"[SALib sobol] same seed repeats exactly: "
        f"{np.array_equal(a['S1'], b['S1']) and np.array_equal(a['ST'], b['ST'])}"
    )
    x = morris_sample.sample(PROBLEM, 100, num_levels=4, seed=11)
    m = morris_analyze.analyze(PROBLEM, x, ishigami(x), num_levels=4, seed=11)
    order = np.argsort(-np.asarray(m["mu_star"]))
    print(
        f"[SALib morris r=100] evaluations={len(x)} mu_star="
        f"{[round(float(v), 3) for v in m['mu_star']]} sigma="
        f"{[round(float(v), 3) for v in m['sigma']]} ranking={[f'x{i + 1}' for i in order]}"
    )
    lower, upper = [-math.pi] * 3, [math.pi] * 3
    for name, make in (
        ("LatinHypercube", lambda s: qmc.LatinHypercube(d=3, rng=s)),
        ("Sobol scrambled", lambda s: qmc.Sobol(d=3, rng=s)),
    ):
        p = make(5).random(2**12)
        again = make(5).random(2**12)
        y = ishigami(qmc.scale(p, lower, upper))
        print(
            f"[qmc {name} n=4096 seed=5] mean={y.mean():.4f} (known {known['mean']:.4f}) "
            f"var={y.var(ddof=1):.4f} (known {known['var']:.4f}) "
            f"centred discrepancy={qmc.discrepancy(p):.2e} repeats={np.array_equal(p, again)}"
        )
    p = np.random.default_rng(5).random((2**12, 3))
    y = ishigami(qmc.scale(p, lower, upper))
    print(
        f"[plain Monte Carlo n=4096 seed=5] mean={y.mean():.4f} var={y.var(ddof=1):.4f} "
        f"centred discrepancy={qmc.discrepancy(p):.2e}"
    )


if __name__ == "__main__":
    main()
