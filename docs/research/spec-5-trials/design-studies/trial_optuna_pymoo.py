"""Spec 5 trial: Optuna 5.1.0 TPE on Branin; pymoo 0.6.2 NSGA-II and Optuna NSGA-II on ZDT1.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 venv && VIRTUAL_ENV=$PWD/venv uv pip install optuna==5.1.0 \
        pymoo==0.6.2 numpy==2.5.5
Run (from this folder):
    <venv>/bin/python trial_optuna_pymoo.py > output_optuna_pymoo.txt

Known answers:
- Branin (a=1, b=5.1/(4 pi^2), c=5/pi, r=6, s=10, t=1/(8 pi)) on x1 in [-5, 10],
  x2 in [0, 15]: f* = 0.397887 at (-pi, 12.275), (pi, 2.275), (9.42478, 2.475)
  (Surjanovic and Bingham, sfu.ca/~ssurjano/branin.html).
- ZDT1, m = 30, x_i in [0, 1]: f1 = x1, g = 1 + 9 sum(x2..xm)/(m-1), f2 = g (1 - sqrt(f1/g));
  the Pareto-optimal front is g = 1, so f2 = 1 - sqrt(f1), f1 in [0, 1]
  (Zitzler, Deb and Thiele 2000, Evolutionary Computation 8(2), eq. 7, p. 177).
IGD is pymoo's indicator against 1001 points of that front built here from the formula.
"""

import math
import time

import numpy as np
import optuna
import pymoo
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.indicators.igd import IGD
from pymoo.optimize import minimize

BRANIN_F = 0.397887
BRANIN_X = [(-math.pi, 12.275), (math.pi, 2.275), (9.42478, 2.475)]
F1 = np.linspace(0.0, 1.0, 1001)
ZDT1_FRONT = np.column_stack([F1, 1.0 - np.sqrt(F1)])
M = 30


def branin(x1: float, x2: float) -> float:
    b, c, t = 5.1 / (4 * math.pi**2), 5 / math.pi, 1 / (8 * math.pi)
    return (x2 - b * x1**2 + c * x1 - 6) ** 2 + 10 * (1 - t) * math.cos(x1) + 10


def zdt1(x: np.ndarray) -> tuple[float, float]:
    g = 1.0 + 9.0 * float(np.sum(x[1:])) / (len(x) - 1)
    return float(x[0]), g * (1.0 - math.sqrt(x[0] / g))


def tpe_branin(seed: int, budget: int) -> tuple[float, float, float]:
    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(
        lambda tr: branin(tr.suggest_float("x1", -5, 10), tr.suggest_float("x2", 0, 15)),
        n_trials=budget,
    )
    p = study.best_params
    return study.best_value, p["x1"], p["x2"]


def nearest(x1: float, x2: float) -> float:
    return min(math.dist((x1, x2), point) for point in BRANIN_X)


class ZDT1(ElementwiseProblem):
    def __init__(self) -> None:
        super().__init__(n_var=M, n_obj=2, xl=0.0, xu=1.0)

    def _evaluate(self, x, out, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        out["F"] = list(zdt1(x))


def pymoo_zdt1(seed: int, generations: int) -> tuple[float, int, np.ndarray]:
    res = minimize(ZDT1(), NSGA2(pop_size=100), ("n_gen", generations), seed=seed)
    return float(IGD(ZDT1_FRONT)(res.F)), int(res.algorithm.evaluator.n_eval), res.F


def optuna_zdt1(seed: int, budget: int) -> float:
    sampler = optuna.samplers.NSGAIISampler(seed=seed, population_size=100)
    study = optuna.create_study(directions=["minimize", "minimize"], sampler=sampler)
    study.optimize(
        lambda tr: zdt1(np.array([tr.suggest_float(f"x{i}", 0, 1) for i in range(M)])),
        n_trials=budget,
    )
    front = np.array([t.values for t in study.best_trials])
    return float(IGD(ZDT1_FRONT)(front))


def constrained_optuna(seed: int) -> tuple[float, float, float]:
    """Branin with x1 >= 5 written as a constraint (5 - x1 <= 0), not as a bound."""
    sampler = optuna.samplers.TPESampler(seed=seed)

    def objective(tr: optuna.Trial) -> float:
        x1, x2 = tr.suggest_float("x1", -5, 10), tr.suggest_float("x2", 0, 15)
        tr.set_user_attr("c", 5.0 - x1)
        tr.set_constraint("x1_at_least_5", 5.0 - x1)  # Optuna 5: feasible at 0 or less
        return branin(x1, x2)

    study = optuna.create_study(sampler=sampler)
    study.optimize(objective, n_trials=200)
    feasible = [t for t in study.trials if t.user_attrs["c"] <= 0]
    best = min(feasible, key=lambda t: t.value)
    return best.value, best.params["x1"], best.params["x2"]


class ConstrainedBranin(ElementwiseProblem):
    def __init__(self) -> None:
        super().__init__(
            n_var=2, n_obj=1, n_ieq_constr=1, xl=np.array([-5.0, 0.0]), xu=np.array([10.0, 15.0])
        )

    def _evaluate(self, x, out, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        out["F"] = branin(x[0], x[1])
        out["G"] = 5.0 - x[0]


def constrained_pymoo(seed: int) -> tuple[float, float, float]:
    from pymoo.algorithms.soo.nonconvex.ga import GA

    res = minimize(ConstrainedBranin(), GA(pop_size=20), ("n_gen", 10), seed=seed)
    return float(res.F[0]), float(res.X[0]), float(res.X[1])


def main() -> None:
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    print(f"optuna={optuna.__version__} pymoo={pymoo.__version__} numpy={np.__version__}")
    print(
        f"branin at the three published minima: "
        f"{[round(branin(*p), 6) for p in BRANIN_X]} (published 0.397887)"
    )
    for budget in (50, 100, 200):
        for seed in (1, 2, 3):
            f, x1, x2 = tpe_branin(seed, budget)
            print(
                f"[optuna TPE branin] budget={budget} seed={seed} best={f:.6f} "
                f"gap={f - BRANIN_F:.2e} at ({x1:.4f}, {x2:.4f}) "
                f"distance to nearest minimum={nearest(x1, x2):.4f}"
            )
    print(
        f"[optuna TPE branin] seed 1 budget 100 repeats exactly: "
        f"{tpe_branin(1, 100) == tpe_branin(1, 100)}"
    )
    for name, run in (
        ("optuna TPE 200", constrained_optuna),
        ("pymoo GA 20x10", constrained_pymoo),
    ):
        f, x1, x2 = run(1)
        print(
            f"[{name} branin s.t. x1 >= 5, seed 1] best={f:.6f} at ({x1:.4f}, {x2:.4f}) "
            f"feasible={x1 >= 5} (known 0.397887 at (9.42478, 2.475))"
        )
    for generations in (20, 200):
        for seed in (1, 2):
            start = time.perf_counter()
            igd, evals, _ = pymoo_zdt1(seed, generations)
            print(
                f"[pymoo NSGA-II zdt1] generations={generations} seed={seed} "
                f"evaluations={evals} IGD={igd:.5f} seconds={time.perf_counter() - start:.1f}"
            )
    a, b = pymoo_zdt1(1, 50)[2], pymoo_zdt1(1, 50)[2]
    print(f"[pymoo NSGA-II zdt1] seed 1, 50 generations repeats exactly: {np.array_equal(a, b)}")
    for seed, budget in ((1, 2000), (2, 2000), (1, 20000)):
        start = time.perf_counter()
        igd = optuna_zdt1(seed, budget)
        print(
            f"[optuna NSGAIISampler zdt1] trials={budget} seed={seed} IGD={igd:.5f} "
            f"seconds={time.perf_counter() - start:.1f}"
        )


if __name__ == "__main__":
    main()
