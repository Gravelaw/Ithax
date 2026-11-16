"""Spec 5 trial: OpenMDAO 3.45.2 drives SciPy SLSQP on known optima, in process and through
an external process (ExternalCodeComp), plus a seeded Latin hypercube DOE (which needs the
optional pydoe package; not installed here, so the script reports it as not run).

Install (scratch venv, outside the repository):
    uv venv -p 3.12 venv && VIRTUAL_ENV=$PWD/venv uv pip install openmdao==3.45.2 \
        scipy==1.18.1 numpy==2.5.5
Run (from this folder):
    <venv>/bin/python trial_openmdao.py > output_openmdao.txt

Known answers:
- Paraboloid f = (x-3)^2 + xy + (y+4)^2 - 3: minimum at x = 20/3, y = -22/3 (OpenMDAO
  "Paraboloid - A Single-Discipline Model"); f there = -246/9 = -27.3333 (from the formula).
- Rosenbrock 2-D: f = 0 at (1, 1) (Surjanovic and Bingham, sfu.ca/~ssurjano/rosen.html).
The optimizer is SciPy's SLSQP; derivatives are finite differences (method="fd").
"""

import pathlib
import shutil
import sys
import tempfile
import time

import numpy as np
import openmdao.api as om

HERE = pathlib.Path(__file__).resolve().parent
PARAB_X, PARAB_Y = 20.0 / 3.0, -22.0 / 3.0
PARAB_F = -246.0 / 9.0


class Paraboloid(om.ExplicitComponent):
    def setup(self) -> None:
        self.add_input("x", 0.0)
        self.add_input("y", 0.0)
        self.add_output("f", 0.0)

    def setup_partials(self) -> None:
        self.declare_partials("f", ["x", "y"], method="fd")

    def compute(self, inputs, outputs) -> None:  # type: ignore[no-untyped-def]
        x, y = inputs["x"][0], inputs["y"][0]
        outputs["f"] = (x - 3.0) ** 2 + x * y + (y + 4.0) ** 2 - 3.0


class Rosenbrock(om.ExplicitComponent):
    def setup(self) -> None:
        self.add_input("x", np.zeros(2))
        self.add_output("f", 0.0)

    def setup_partials(self) -> None:
        self.declare_partials("f", "x", method="fd")

    def compute(self, inputs, outputs) -> None:  # type: ignore[no-untyped-def]
        x = inputs["x"]
        outputs["f"] = 100.0 * (x[1] - x[0] ** 2) ** 2 + (1.0 - x[0]) ** 2


class ExternalParaboloid(om.ExternalCodeComp):
    """Black-box wrap: write input.txt, run a separate Python process, read output.txt."""

    def initialize(self) -> None:
        super().initialize()
        self.options.declare("poll", default=0.0, desc="seconds between polls; 0 = default")
        self.calls = 0

    def setup(self) -> None:
        self.add_input("x", 0.0)
        self.add_input("y", 0.0)
        self.add_output("f", 0.0)
        self.options["external_input_files"] = ["input.txt"]
        self.options["external_output_files"] = ["output.txt"]
        self.options["command"] = [
            sys.executable,
            str(HERE / "external_paraboloid.py"),
            "input.txt",
            "output.txt",
        ]
        self.options["timeout"] = 30.0
        # With poll_delay 0 OpenMDAO polls every max(0.1, timeout / 100) seconds (shell_proc).
        self.options["poll_delay"] = self.options["poll"]

    def setup_partials(self) -> None:
        self.declare_partials("f", ["x", "y"], method="fd")

    def compute(self, inputs, outputs) -> None:  # type: ignore[no-untyped-def]
        pathlib.Path("input.txt").write_text(
            f"{float(inputs['x'][0])!r} {float(inputs['y'][0])!r}\n", encoding="utf-8"
        )
        super().compute(inputs, outputs)
        outputs["f"] = float(pathlib.Path("output.txt").read_text(encoding="utf-8"))
        self.calls += 1


def slsqp(prob: om.Problem) -> None:
    prob.driver = om.ScipyOptimizeDriver(optimizer="SLSQP", tol=1e-9, disp=False)


def paraboloid(comp: om.ExplicitComponent, label: str) -> None:
    prob = om.Problem(reports=False)
    prob.model.add_subsystem("p", comp, promotes=["*"])
    prob.model.add_design_var("x", lower=-50.0, upper=50.0)
    prob.model.add_design_var("y", lower=-50.0, upper=50.0)
    prob.model.add_objective("f")
    slsqp(prob)
    prob.setup()
    prob.set_val("x", 3.0)
    prob.set_val("y", -4.0)
    start = time.perf_counter()
    failed = prob.run_driver().success is False
    seconds = time.perf_counter() - start
    x, y, f = prob.get_val("x")[0], prob.get_val("y")[0], prob.get_val("f")[0]
    print(
        f"[{label}] SLSQP failed={failed} x={x:.6f} y={y:.6f} f={f:.6f} "
        f"(known x={PARAB_X:.6f} y={PARAB_Y:.6f} f={PARAB_F:.6f}) "
        f"|f-f*|={abs(f - PARAB_F):.2e} seconds={seconds:.2f}"
    )
    if isinstance(comp, ExternalParaboloid):
        print(f"[{label}] external process calls: {comp.calls}")


def rosenbrock() -> None:
    prob = om.Problem(reports=False)
    prob.model.add_subsystem("r", Rosenbrock(), promotes=["*"])
    prob.model.add_design_var("x", lower=-5.0, upper=10.0)
    prob.model.add_objective("f")
    slsqp(prob)
    prob.setup()
    prob.set_val("x", np.array([-1.2, 1.0]))
    failed = prob.run_driver().success is False
    x, f = prob.get_val("x"), prob.get_val("f")[0]
    print(
        f"[rosenbrock] SLSQP from (-1.2, 1) failed={failed} x=({x[0]:.6f}, {x[1]:.6f}) "
        f"f={f:.3e} (known (1, 1), 0) |x-x*|={np.linalg.norm(x - 1.0):.2e}"
    )


def lhs_doe(seed: int) -> list[tuple[float, float, float]]:
    prob = om.Problem(reports=False)
    prob.model.add_subsystem("p", Paraboloid(), promotes=["*"])
    prob.model.add_design_var("x", lower=-10.0, upper=10.0)
    prob.model.add_design_var("y", lower=-10.0, upper=10.0)
    prob.model.add_objective("f")
    prob.driver = om.DOEDriver(om.LatinHypercubeGenerator(samples=5, seed=seed))
    rec = om.SqliteRecorder("doe.sql")
    prob.driver.add_recorder(rec)
    prob.setup()
    prob.run_driver()
    prob.cleanup()
    cases = om.CaseReader("doe.sql").get_cases("driver")
    return [(c["x"][0], c["y"][0], c["f"][0]) for c in cases]


def raw_subprocess_seconds() -> None:
    """The same external script run 17 times with subprocess.run, for comparison."""
    import subprocess

    pathlib.Path("input.txt").write_text("1.0 2.0\n", encoding="utf-8")
    command = [sys.executable, str(HERE / "external_paraboloid.py"), "input.txt", "output.txt"]
    start = time.perf_counter()
    for _ in range(17):
        subprocess.run(command, check=True)
    print(f"[subprocess.run x17] seconds={time.perf_counter() - start:.2f}")


def main() -> None:
    import openmdao
    import scipy

    print(f"openmdao={openmdao.__version__} scipy={scipy.__version__} numpy={np.__version__}")
    work = pathlib.Path(tempfile.mkdtemp(prefix="omtrial-"))
    try:
        import os

        os.chdir(work)
        paraboloid(Paraboloid(), "paraboloid in-process")
        paraboloid(ExternalParaboloid(), "paraboloid ExternalCodeComp poll default")
        paraboloid(ExternalParaboloid(poll=0.005), "paraboloid ExternalCodeComp poll 0.005 s")
        rosenbrock()
        raw_subprocess_seconds()
        try:
            first, second = lhs_doe(seed=7), lhs_doe(seed=7)
        except RuntimeError as error:
            print(f"[lhs] LatinHypercubeGenerator not run: {str(error).splitlines()[0]}")
            return
        for x, y, f in first:
            print(f"[lhs seed=7] x={x:.6f} y={y:.6f} f={f:.6f}")
        print(f"[lhs] same seed gives same points: {first == second}")
    finally:
        os.chdir(HERE)
        shutil.rmtree(work)


if __name__ == "__main__":
    main()
