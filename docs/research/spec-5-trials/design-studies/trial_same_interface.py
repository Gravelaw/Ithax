"""Spec 5 trial: one evaluate(values) -> metrics interface, two engines (in-process and a
separate process exchanging JSON files), driven by Optuna, pymoo, SciPy and SALib alike.

This is the shape spec 5's row "A design study optimizes a process model and a physical
system model with the same interface" needs: the study layer sees only named inputs with
bounds and named outputs, never the engine. The real Ithax engines are not used here.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 venv && VIRTUAL_ENV=$PWD/venv uv pip install optuna==5.1.0 \
        pymoo==0.6.2 salib==1.6.0 scipy==1.18.1 numpy==2.5.5
Run (from this folder):
    <venv>/bin/python trial_same_interface.py > output_same_interface.txt

Known answer: Branin minimum 0.397887 (sfu.ca/~ssurjano/branin.html).
"""

import json
import math
import pathlib
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from multiprocessing.pool import Pool

import numpy as np
import optuna
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize as pymoo_minimize
from pymoo.parallelization import StarmapParallelization
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample
from scipy.optimize import minimize as scipy_minimize
from scipy.stats import qmc

HERE = pathlib.Path(__file__).resolve().parent
BOUNDS = {"x1": (-5.0, 10.0), "x2": (0.0, 15.0)}
NAMES = list(BOUNDS)
Evaluate = Callable[[dict[str, float]], dict[str, float]]


def in_process(values: dict[str, float]) -> dict[str, float]:
    x1, x2 = values["x1"], values["x2"]
    b, c, t = 5.1 / (4 * math.pi**2), 5 / math.pi, 1 / (8 * math.pi)
    return {"f": (x2 - b * x1**2 + c * x1 - 6) ** 2 + 10 * (1 - t) * math.cos(x1) + 10}


def file_engine(values: dict[str, float]) -> dict[str, float]:
    with tempfile.TemporaryDirectory(prefix="eval-") as folder:
        work = pathlib.Path(folder)
        (work / "input.json").write_text(json.dumps(values), encoding="utf-8")
        subprocess.run(
            [sys.executable, str(HERE / "external_branin.py"), "input.json", "output.json"],
            cwd=work,
            check=True,
            timeout=30,
        )
        return json.loads((work / "output.json").read_text(encoding="utf-8"))


def as_dict(x: np.ndarray) -> dict[str, float]:
    return {name: float(v) for name, v in zip(NAMES, x, strict=True)}


def by_optuna(evaluate: Evaluate, seed: int, budget: int) -> float:
    study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(
        lambda tr: evaluate({n: tr.suggest_float(n, *BOUNDS[n]) for n in NAMES})["f"],
        n_trials=budget,
    )
    return study.best_value


class Study(ElementwiseProblem):
    def __init__(self, evaluate: Evaluate, **kwargs) -> None:  # type: ignore[no-untyped-def]
        lower, upper = zip(*BOUNDS.values(), strict=True)
        super().__init__(n_var=2, n_obj=1, xl=np.array(lower), xu=np.array(upper), **kwargs)
        self.evaluate_one = evaluate

    def _evaluate(self, x, out, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        out["F"] = self.evaluate_one(as_dict(x))["f"]


def by_pymoo(evaluate: Evaluate, seed: int, pool: Pool | None = None) -> float:
    extra = {"elementwise_runner": StarmapParallelization(pool.starmap)} if pool else {}
    res = pymoo_minimize(Study(evaluate, **extra), GA(pop_size=20), ("n_gen", 10), seed=seed)
    return float(res.F[0])


def by_scipy(evaluate: Evaluate) -> tuple[float, int]:
    res = scipy_minimize(
        lambda x: evaluate(as_dict(x))["f"],
        x0=[2.5, 7.5],
        method="Nelder-Mead",
        bounds=list(BOUNDS.values()),
        options={"xatol": 1e-6, "fatol": 1e-9},
    )
    return float(res.fun), int(res.nfev)


def sweep(evaluate: Evaluate) -> list[float]:
    return [
        round(evaluate({"x1": float(x1), "x2": 2.275})["f"], 4) for x1 in np.linspace(-5, 10, 7)
    ]


def sensitivity(evaluate: Evaluate) -> tuple[list[float], list[float]]:
    problem = {"num_vars": 2, "names": NAMES, "bounds": list(BOUNDS.values())}
    x = sobol_sample.sample(problem, 64, calc_second_order=False, seed=3)
    y = np.array([evaluate(as_dict(row))["f"] for row in x])
    r = sobol_analyze.analyze(problem, y, calc_second_order=False, seed=3)
    return [round(float(v), 4) for v in r["S1"]], [round(float(v), 4) for v in r["ST"]]


def lhs_spread(evaluate: Evaluate) -> tuple[float, float]:
    p = qmc.scale(qmc.LatinHypercube(d=2, rng=4).random(64), *zip(*BOUNDS.values(), strict=True))
    y = np.array([evaluate(as_dict(row))["f"] for row in p])
    return round(float(y.mean()), 4), round(float(np.percentile(y, 95)), 4)


def run_all(label: str, evaluate: Evaluate) -> dict[str, object]:
    start = time.perf_counter()
    out: dict[str, object] = {
        "optuna TPE best (40 trials, seed 1)": round(by_optuna(evaluate, 1, 40), 6),
        "pymoo GA best (20 x 10, seed 1)": round(by_pymoo(evaluate, 1), 6),
        "scipy Nelder-Mead best, evaluations": by_scipy(evaluate),
        "sweep x1 at x2=2.275": sweep(evaluate),
        "LHS 64 mean, 95th percentile": lhs_spread(evaluate),
        "SALib Sobol N=64 S1, ST": sensitivity(evaluate),
    }
    print(f"[{label}] seconds={time.perf_counter() - start:.1f}")
    for key, value in out.items():
        print(f"  {key}: {value}")
    return out


def main() -> None:
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    print(f"optuna={optuna.__version__} numpy={np.__version__} (known Branin min 0.397887)")
    a = run_all("in-process engine", in_process)
    start = time.perf_counter()
    for _ in range(20):
        file_engine({"x1": 1.0, "x2": 2.0})
    print(f"[file engine] seconds per evaluation={(time.perf_counter() - start) / 20:.3f}")
    b = run_all("separate-process file engine", file_engine)
    print(f"same results from both engines: {a == b}")
    with Pool(4) as pool:
        start = time.perf_counter()
        parallel = by_pymoo(file_engine, 1, pool)
        print(
            f"[pymoo GA, file engine, 4 worker processes] best={parallel:.6f} "
            f"seconds={time.perf_counter() - start:.1f} same as serial: "
            f"{round(parallel, 6) == a['pymoo GA best (20 x 10, seed 1)']}"
        )


if __name__ == "__main__":
    main()
