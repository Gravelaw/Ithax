"""Spec 5 trial: the pendulum benchmark in Project Chrono (PyChrono 9.0.1).

Run by the CI workflow `.github/workflows/spec5-trials.yml` in a conda environment with
`projectchrono::pychrono=9.0.1` (Python 3.12):
    python pendulum.py

A 1 kg body with negligible inertia about its centre, on a revolute joint 1 m above it,
g = 9.80665 m/s^2, released at rest at 10 and 90 degrees. The period is measured from
upward zero crossings of the angle, linearly interpolated, over 10 periods. Known answer:
T = 4 sqrt(L/g) K(sin(theta0/2)) = 2.010235893 s at 10 deg and 2.368246346 s at 90 deg
(docs/research/spec-5-trials/benchmarks/output.txt). Pass rule proposed in spec 5:
relative 1e-6. Each time stepper is tried in turn; a failure is printed, not hidden.
"""

import math

import pychrono as chrono

L, G = 1.0, 9.80665
EXACT = {10: 2.010235893, 90: 2.368246346}


def build(degrees: float, stepper: str) -> tuple[chrono.ChSystemNSC, chrono.ChBody]:
    system = chrono.ChSystemNSC()
    system.SetGravitationalAcceleration(chrono.ChVector3d(0, -G, 0))
    ground = chrono.ChBody()
    ground.SetFixed(True)
    system.Add(ground)
    bob = chrono.ChBody()
    bob.SetMass(1.0)
    bob.SetInertiaXX(chrono.ChVector3d(1e-9, 1e-9, 1e-9))
    theta = math.radians(degrees)
    bob.SetPos(chrono.ChVector3d(L * math.sin(theta), -L * math.cos(theta), 0))
    system.Add(bob)
    joint = chrono.ChLinkLockRevolute()  # rotation about the frame's z axis
    joint.Initialize(ground, bob, chrono.ChFramed(chrono.ChVector3d(0, 0, 0), chrono.QUNIT))
    system.Add(joint)
    if stepper == "HHT":
        system.SetSolverType(chrono.ChSolver.Type_MINRES)
        system.SetTimestepperType(chrono.ChTimestepper.Type_HHT)
    elif stepper == "EULER_IMPLICIT_PROJECTED":
        system.SetTimestepperType(chrono.ChTimestepper.Type_EULER_IMPLICIT_PROJECTED)
    return system, bob


def period(degrees: float, stepper: str, dt: float) -> float:
    system, bob = build(degrees, stepper)
    crossings: list[float] = []
    previous = math.atan2(bob.GetPos().x, -bob.GetPos().y)
    while len(crossings) < 11 and system.GetChTime() < 40:
        t0 = system.GetChTime()
        system.DoStepDynamics(dt)
        angle = math.atan2(bob.GetPos().x, -bob.GetPos().y)
        if previous < 0 <= angle:
            crossings.append(t0 + dt * (-previous) / (angle - previous))
        previous = angle
    if len(crossings) < 11:
        raise RuntimeError(f"only {len(crossings)} crossings in 40 s")
    return (crossings[-1] - crossings[0]) / 10


def main() -> None:
    print("pychrono", chrono.GetChronoVersion() if hasattr(chrono, "GetChronoVersion") else "?")
    for degrees in (10, 90):
        for stepper in ("EULER_IMPLICIT_LINEARIZED", "EULER_IMPLICIT_PROJECTED", "HHT"):
            for dt in (1e-3, 1e-4):
                try:
                    t = period(degrees, stepper, dt)
                except Exception as error:  # the trial records what happened
                    print(
                        f"{degrees:>2} deg, {stepper}, dt {dt:g}: failed: "
                        f"{type(error).__name__}: {error}"
                    )
                    continue
                rel = (t - EXACT[degrees]) / EXACT[degrees]
                print(
                    f"{degrees:>2} deg, {stepper}, dt {dt:g} s: T {t:.9f} s, "
                    f"exact {EXACT[degrees]:.9f} s, relative error {rel:+.2e}, "
                    f"within 1e-6: {abs(rel) <= 1e-6}"
                )


if __name__ == "__main__":
    main()
