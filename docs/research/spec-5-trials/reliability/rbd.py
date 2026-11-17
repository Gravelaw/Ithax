"""Trial 2: reliability block diagrams, closed form against RePyability and Monte Carlo.

Formulas (sources read 2026-11-16):
- Series: R = prod R_i; parallel: R = 1 - prod (1 - R_i); r-out-of-n with
  identical parts: R = sum_{i=r..n} C(n,i) R^i (1-R)^(n-i).
  NIST/SEMATECH e-Handbook 8.1.8.2, 8.1.8.3, 8.1.8.4.
- 2oo3 of identical parts: R = 3p^2 - 2p^3; MTTF of koon with constant rate
  lambda: (1/lambda) sum_{x=k..n} 1/x, so 1oo2 = 3/(2 lambda) = 1500 for
  lambda = 0.001 (Rausand, "System Reliability Theory" ch. 4 slides, Example 4.9
  cont. 3) and 2oo3 = 5/(6 lambda). Rausand slides 14, 27, 29, 32-33.
- The SIF structure (PT 2oo3, LS, SDV 1oo2 in series) is Lundteigen and Rausand,
  SIS book ch. 5 slides 8-10. Its component probabilities below are chosen
  here, not published.

Install (scratch venv, Python 3.12, Linux):
    VIRTUAL_ENV=venv uv pip install repyability==0.19.1 surpyval==0.28 numpy==2.5.5
Run:
    venv/bin/python rbd.py > output-rbd.txt
"""

from importlib.metadata import version
from math import comb

import numpy as np
import repyability as rp
import surpyval as sv

SEED = 20261116
N_MC = 1_000_000


def fixed(q: float) -> object:
    """A component that has failed with probability q."""
    return sv.FixedEventProbability.from_params([q])


def k_of_n(r: float, k: int, n: int) -> float:
    return sum(comb(n, i) * r**i * (1 - r) ** (n - i) for i in range(k, n + 1))


def line(
    name: str, closed: float, lib: float, mc: float | None = None, se: float | None = None
) -> None:
    text = f"{name:<44} closed={closed:.10f} repyability={lib:.10f} diff={lib - closed:+.1e}"
    if mc is not None and se is not None:
        text += f" mc={mc:.6f} (|mc-closed|/se={abs(mc - closed) / se:.2f})"
    print(text)


def mc_estimate(works: np.ndarray) -> tuple[float, float]:
    p = float(works.mean())
    return p, float(np.sqrt(p * (1 - p) / works.size))


def series_parallel(rng: np.random.Generator) -> None:
    r1, r2, r3, r4 = 0.95, 0.90, 0.80, 0.80
    closed = r1 * r2 * (1 - (1 - r3) * (1 - r4))
    edges = [("in", "c1"), ("c1", "c2"), ("c2", "c3"), ("c2", "c4"), ("c3", "out"), ("c4", "out")]
    rbd = rp.NonRepairableRBD(
        edges,
        {c: fixed(1 - r) for c, r in zip(["c1", "c2", "c3", "c4"], [r1, r2, r3, r4], strict=True)},
    )
    up = rng.random((N_MC, 4)) < np.array([r1, r2, r3, r4])
    works = up[:, 0] & up[:, 1] & (up[:, 2] | up[:, 3])
    line("series-parallel R1 R2 (1-(1-R3)(1-R4))", closed, float(rbd.sf()), *mc_estimate(works))


def two_of_three(rng: np.random.Generator) -> None:
    p = 0.9
    closed = 3 * p**2 - 2 * p**3
    edges = [("in", "a"), ("in", "b"), ("in", "c"), ("a", "out"), ("b", "out"), ("c", "out")]
    rbd = rp.NonRepairableRBD(edges, {x: fixed(1 - p) for x in "abc"}, k={"out": 2})
    up = rng.random((N_MC, 3)) < p
    works = up.sum(axis=1) >= 2
    line("2oo3, p=0.9: 3p^2-2p^3", closed, float(rbd.sf()), *mc_estimate(works))
    print(f"{'  binomial sum k_of_n(0.9, 2, 3)':<44} {k_of_n(p, 2, 3):.10f}")


def sif(rng: np.random.Generator) -> None:
    q_pt, q_ls, q_sdv = 0.05, 0.01, 0.10
    closed = k_of_n(1 - q_pt, 2, 3) * (1 - q_ls) * (1 - q_sdv**2)
    edges = [
        ("in", "pt1"),
        ("in", "pt2"),
        ("in", "pt3"),
        ("pt1", "ls"),
        ("pt2", "ls"),
        ("pt3", "ls"),
        ("ls", "sdv1"),
        ("ls", "sdv2"),
        ("sdv1", "out"),
        ("sdv2", "out"),
    ]
    models = {
        "pt1": fixed(q_pt),
        "pt2": fixed(q_pt),
        "pt3": fixed(q_pt),
        "ls": fixed(q_ls),
        "sdv1": fixed(q_sdv),
        "sdv2": fixed(q_sdv),
    }
    rbd = rp.NonRepairableRBD(edges, models, k={"ls": 2})
    up = rng.random((N_MC, 6)) >= np.array([q_pt] * 3 + [q_ls] + [q_sdv] * 2)
    works = (up[:, :3].sum(axis=1) >= 2) & up[:, 3] & (up[:, 4] | up[:, 5])
    line("SIF: PT 2oo3, LS, SDV 1oo2 (series)", closed, float(rbd.sf()), *mc_estimate(works))
    print(f"  repyability minimal cut sets: {sorted(sorted(c) for c in rbd.minimal_cut_sets())}")


def mttf() -> None:
    lam = 0.001
    exp = sv.Exponential.from_params([lam])
    par = rp.NonRepairableRBD(
        [("in", "a"), ("in", "b"), ("a", "out"), ("b", "out")], {"a": exp, "b": exp}
    )
    line("MTTF 1oo2, lambda=0.001 (published 1500)", 3 / (2 * lam), float(par.mean()))
    edges = [("in", "a"), ("in", "b"), ("in", "c"), ("a", "out"), ("b", "out"), ("c", "out")]
    voted = rp.NonRepairableRBD(edges, {x: exp for x in "abc"}, k={"out": 2})
    line("MTTF 2oo3, lambda=0.001: 5/(6 lambda)", 5 / (6 * lam), float(voted.mean()))
    t = 500.0
    r = float(np.exp(-lam * t))
    line("R(500) 2oo3 exp: 3e^-2lt - 2e^-3lt", 3 * r**2 - 2 * r**3, float(voted.sf(t)))


def main() -> None:
    print(
        f"repyability {version('repyability')}, surpyval {version('surpyval')}, "
        f"numpy {version('numpy')}; "
        f"Monte Carlo n={N_MC}, numpy default_rng seed {SEED}"
    )
    rng = np.random.default_rng(SEED)
    series_parallel(rng)
    two_of_three(rng)
    sif(rng)
    mttf()


if __name__ == "__main__":
    main()
