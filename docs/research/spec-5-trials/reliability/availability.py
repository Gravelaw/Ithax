"""Trial 4: steady-state and point availability of repairable units.

Known answers:
- one unit, exponential up times (MTTF 100) and repairs (MTTR 25):
  A = MTTF/(MTTF + MTTR) = 100/125 = 0.8 (alternating renewal process; the same
  case and value as the Ithax benchmark benchmarks/failure, spec 2, AKS-107).
- point availability with constant rates lambda = 1/MTTF, mu = 1/MTTR, starting up:
  A(t) = mu/(lambda+mu) + lambda/(lambda+mu) exp(-(lambda+mu) t) (the complement
  of q(t) = [lambda/(lambda+mu)] [1 - exp(-(lambda+mu) t)] quoted in pfta 0.4.0's
  computation.py docstring; the standard two-state Markov result).
- two such units in parallel, each with its own repair: A = 1 - (1 - 0.8)^2 = 0.96;
  in series: A = 0.8^2 = 0.64 (independent components; NIST 8.1.8.2-8.1.8.3
  applied to availabilities).

Install (scratch venv, Python 3.12, Linux):
    VIRTUAL_ENV=venv uv pip install repyability==0.19.1 surpyval==0.28
Run:
    venv/bin/python availability.py > output-availability.txt
"""

from importlib.metadata import version
from math import exp

import repyability as rp
import surpyval as sv

MTTF, MTTR = 100.0, 25.0
SEED = 20261116


def unit() -> dict[str, object]:
    return {
        "reliability": sv.Exponential.from_params([1 / MTTF]),
        "repairability": sv.Exponential.from_params([1 / MTTR]),
    }


def main() -> None:
    print(f"repyability {version('repyability')}, surpyval {version('surpyval')}")
    one = rp.RepairableRBD([("in", "u"), ("u", "out")], {"u": unit()})
    print(
        f"single unit  closed=0.8000000000 "
        f"repyability mean_availability={one.mean_availability():.10f}"
    )
    lam, mu = 1 / MTTF, 1 / MTTR
    for t in (10.0, 50.0, 200.0):
        closed = mu / (lam + mu) + lam / (lam + mu) * exp(-(lam + mu) * t)
        lib = float(one.point_availability(t))
        print(
            f"A({t:>5}) closed={closed:.10f} "
            f"repyability point_availability={lib:.10f} diff={lib - closed:+.1e}"
        )
    par = rp.RepairableRBD(
        [("in", "a"), ("in", "b"), ("a", "out"), ("b", "out")], {"a": unit(), "b": unit()}
    )
    ser = rp.RepairableRBD([("in", "a"), ("a", "b"), ("b", "out")], {"a": unit(), "b": unit()})
    print(f"parallel 1oo2 closed=0.9600000000 repyability={par.mean_availability():.10f}")
    print(f"series       closed=0.6400000000 repyability={ser.mean_availability():.10f}")
    sim = one.availability(100_000.0, mc_samples=200, seed=SEED)
    up = float(sim.uptimes.mean()) / 100_000.0
    print(
        f"simulated single unit over 100000 time units, 200 runs, seed {SEED}: "
        f"mean fraction up {up:.4f}"
    )


if __name__ == "__main__":
    main()
