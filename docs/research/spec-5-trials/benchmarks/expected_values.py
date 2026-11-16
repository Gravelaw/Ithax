"""Spec 5 benchmarks: the exact expected values, computed from closed forms.

Install: any venv with scipy and numpy (scipy 1.18.1 and numpy 2.5.5 used; see output.txt).
Run: <venv>/bin/python expected_values.py > output.txt

Each value comes from a formula, solved with scipy's root finder or special functions,
never from a simulation. Sources are named in docs/specs/5-systems-and-design.md
"Benchmarks" and the research note of each domain (docs/research/spec-5-*.md).
"""

import math

import scipy
from scipy.optimize import brentq
from scipy.special import ellipk


def sir(n: float, i0: float, beta: float, gamma: float) -> None:
    r0, s0 = beta / gamma, n - i0
    s_inf = brentq(lambda s: s - s0 * math.exp(-r0 * (n - s) / n), 1e-12, n / r0)
    peak = i0 + s0 - (n / r0) * (1 + math.log(r0 * s0 / n))
    print(
        f"SIR N={n:g} I0={i0:g} beta={beta} gamma={gamma}: R0 {r0:g}, "
        f"S_inf {s_inf:.6f}, final size N-S_inf {n - s_inf:.6f}, "
        f"peak I {peak:.6f} at S = {n / r0:g}"
    )


def lotka_volterra(a: float, b: float, g: float, d: float, x0: float, y0: float) -> None:
    v = d * x0 - g * math.log(x0) + b * y0 - a * math.log(y0)
    print(
        f"Lotka-Volterra a={a} b={b} g={g} d={d} x0={x0} y0={y0}: "
        f"V = d x - g ln x + b y - a ln y = {v:.9f}; equilibrium x={g / d:g}, y={a / b:g}"
    )


def msd(m: float, c: float, k: float, x0: float, t: float) -> None:
    wn, zeta = math.sqrt(k / m), c / (2 * math.sqrt(k * m))
    wd = wn * math.sqrt(1 - zeta**2)
    x = math.exp(-zeta * wn * t) * x0 * (math.cos(wd * t) + zeta * wn / wd * math.sin(wd * t))
    print(
        f"Mass-spring-damper m={m} c={c} k={k} x0={x0} v0=0: wn {wn:g} rad/s, "
        f"zeta {zeta:g}, wd {wd:.9f} rad/s, damped period {2 * math.pi / wd:.9f} s, "
        f"x({t:g} s) = {x:.9f}"
    )


def pendulum(length: float, g: float, degrees: float) -> None:
    theta0 = math.radians(degrees)
    k = math.sin(theta0 / 2)
    t_exact = 4 * math.sqrt(length / g) * ellipk(k**2)  # scipy's ellipk takes m = k^2
    t_small = 2 * math.pi * math.sqrt(length / g)
    print(
        f"Pendulum L={length} m g={g} m/s^2 amplitude {degrees:g} deg: "
        f"T = 4 sqrt(L/g) K(sin(theta0/2)) = {t_exact:.9f} s "
        f"(small-angle {t_small:.9f} s, ratio {t_exact / t_small:.9f})"
    )


def rbd() -> None:
    r1, r2, r3, r4 = 0.95, 0.90, 0.80, 0.80
    series_parallel = r1 * r2 * (1 - (1 - r3) * (1 - r4))
    two_of_three = 3 * 0.9**2 - 2 * 0.9**3
    print(
        f"RBD: R1 R2 (1-(1-R3)(1-R4)) with 0.95, 0.90, 0.80, 0.80 = {series_parallel:.6f}; "
        f"2-out-of-3 with R=0.9: 3R^2-2R^3 = {two_of_three:.6f}"
    )


def main() -> None:
    print("scipy", scipy.__version__)
    sir(1000, 1, 0.5, 0.25)
    sir(1000, 10, 0.5, 0.25)
    lotka_volterra(1.0, 0.1, 1.5, 0.075, 10.0, 5.0)
    msd(1.0, 0.4, 4.0, 1.0, 10.0)
    for deg in (10, 90):
        pendulum(1.0, 9.80665, deg)
    rbd()


if __name__ == "__main__":
    main()
