"""Trial: a two-mass oscillator split into two "engines" and coupled by a simple master.

Research code for docs/research/spec-5-cosimulation.md, not product code.

Install and run (Python 3.12):

    uv venv -p 3.12 <dir>
    VIRTUAL_ENV=<dir> uv pip install scipy==1.14.1 numpy==2.1.3
    <dir>/bin/python docs/research/spec-5-trials/cosimulation/trial_jacobi_zoh.py > output.txt

System (all masses, springs = 1, no damping): wall -c1- m1 -cc- m2 -c2- wall.
    m1 x1'' = -c1 x1 + cc (x2 - x1)
    m2 x2'' = -c2 x2 - cc (x2 - x1)
Initial state x1 = 1, x2 = 0, v1 = v2 = 0.

Known answer (normal modes, omega = 1 and sqrt(3)):
    x1(t) = (cos t + cos(sqrt(3) t)) / 2
    x2(t) = (cos t - cos(sqrt(3) t)) / 2
Energy E = (v1^2 + v2^2)/2 + (x1^2 + (x2 - x1)^2 + x2^2)/2 = 1 for all t.

Engine 1 integrates (x1, v1) with x2 as an input; engine 2 integrates (x2, v2) with x1 as
an input. Every subsystem is integrated by scipy.integrate.solve_ivp (RK45, rtol 1e-10,
atol 1e-12). The master only exchanges values at communication points t = n H and holds
each input constant over the step (zero-order hold). Jacobi: both engines use the other's
value at t = nH. Gauss-Seidel: engine 1 steps first; engine 2 holds engine 1's new value
x1((n+1)H) over the step.

The growth factor per macro step is the spectral radius of the linear map
(x1, v1, x2, v2)(nH) -> (x1, v1, x2, v2)((n+1)H), built column by column by running one
master step from each unit vector (the map is linear because the system is).
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import solve_ivp

C1 = C2 = CC = 1.0
M1 = M2 = 1.0
T_END = 50.0
RTOL = 1e-10
ATOL = 1e-12
Vec = NDArray[np.float64]


def _engine(state: Vec, u: float, h: float, c_own: float, mass: float) -> Vec:
    """Advance one mass by h with the other mass's position held at u."""

    def rhs(_t: float, y: Vec) -> list[float]:
        x, v = y
        return [v, (-c_own * x + CC * (u - x)) / mass]

    sol = solve_ivp(rhs, (0.0, h), state, method="RK45", rtol=RTOL, atol=ATOL)
    return np.asarray(sol.y[:, -1], dtype=np.float64)


def master_step(y: Vec, h: float, scheme: str) -> Vec:
    """One macro step of the master; y is (x1, v1, x2, v2)."""
    s1 = _engine(y[0:2], float(y[2]), h, C1, M1)
    u2 = float(s1[0]) if scheme == "gauss-seidel" else float(y[0])
    s2 = _engine(y[2:4], u2, h, C2, M2)
    return np.concatenate([s1, s2])


def coupled_run(h: float, scheme: str) -> tuple[Vec, Vec]:
    n_steps = round(T_END / h)
    times = np.arange(n_steps + 1, dtype=np.float64) * h
    ys = np.zeros((n_steps + 1, 4))
    ys[0] = [1.0, 0.0, 0.0, 0.0]
    for n in range(n_steps):
        ys[n + 1] = master_step(ys[n], h, scheme)
    return times, ys


def monolithic(times: Vec) -> Vec:
    def rhs(_t: float, y: Vec) -> list[float]:
        x1, v1, x2, v2 = y
        return [v1, (-C1 * x1 + CC * (x2 - x1)) / M1, v2, (-C2 * x2 - CC * (x2 - x1)) / M2]

    sol = solve_ivp(
        rhs,
        (0.0, T_END),
        [1.0, 0.0, 0.0, 0.0],
        method="DOP853",
        t_eval=times,
        rtol=1e-12,
        atol=1e-14,
    )
    return np.asarray(sol.y.T, dtype=np.float64)


def analytic(times: Vec) -> Vec:
    w2 = math.sqrt(3.0)
    x1 = 0.5 * (np.cos(times) + np.cos(w2 * times))
    x2 = 0.5 * (np.cos(times) - np.cos(w2 * times))
    v1 = 0.5 * (-np.sin(times) - w2 * np.sin(w2 * times))
    v2 = 0.5 * (-np.sin(times) + w2 * np.sin(w2 * times))
    return np.stack([x1, v1, x2, v2], axis=1)


def energy(y: Vec) -> Vec:
    x1, v1, x2, v2 = y[:, 0], y[:, 1], y[:, 2], y[:, 3]
    return np.asarray(0.5 * (v1**2 + v2**2) + 0.5 * (x1**2 + (x2 - x1) ** 2 + x2**2))


def growth_factor(h: float, scheme: str) -> float:
    cols = [master_step(np.eye(4)[k], h, scheme) for k in range(4)]
    return float(max(abs(np.linalg.eigvals(np.stack(cols, axis=1)))))


def main() -> None:
    import scipy

    print(f"scipy {scipy.__version__}, numpy {np.__version__}, T_END {T_END}")
    times = np.linspace(0.0, T_END, 5001)
    ref = analytic(times)
    mono = monolithic(times)
    print(
        f"monolithic solve_ivp DOP853 vs analytic: max|x1 err| = "
        f"{np.max(np.abs(mono[:, 0] - ref[:, 0])):.3e}, "
        f"energy at T_END = {energy(mono)[-1]:.12f}"
    )
    print()
    print(
        "scheme        H      macro steps  max|x1 err|  max|x2 err|  E(T_END)    "
        "growth/step    growth over T_END"
    )
    for scheme in ("jacobi", "gauss-seidel"):
        for h in (0.001, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0):
            t, y = coupled_run(h, scheme)
            exact = analytic(t)
            e1 = np.max(np.abs(y[:, 0] - exact[:, 0]))
            e2 = np.max(np.abs(y[:, 2] - exact[:, 2]))
            rho = growth_factor(h, scheme)
            print(
                f"{scheme:12s} {h:6.3f} {len(t) - 1:11d}  {e1:11.3e}  {e2:11.3e}  "
                f"{energy(y)[-1]:10.4e}  {rho:13.9f}  {rho ** (T_END / h):13.4e}"
            )


if __name__ == "__main__":
    main()
