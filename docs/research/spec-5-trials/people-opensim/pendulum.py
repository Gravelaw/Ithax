"""Spec 5 research trial: a simple pendulum built in the OpenSim 4.6 Python API.

Install and run (research code, not product code):

    uv venv -p 3.12 venv
    VIRTUAL_ENV=venv uv pip install opensim==4.6 scipy==1.18.1
    venv/bin/python -I pendulum.py > output.txt

Model: one body of mass 1 kg with its mass at a point (zero inertia about its
centre of mass) hangs on a pin joint 1 m above the mass; gravity 9.80665 m/s^2.
OpenSim (Simbody's integrator) integrates the motion; this script only reads
the recorded joint angle and finds the times where it crosses zero, by linear
interpolation between recorded samples. The period is twice the mean spacing
of the zero crossings.

Known answer (spec 5 benchmark "Simple pendulum"): the exact large-amplitude
period T = 4 sqrt(L/g) K(k), k = sin(theta0/2), K the complete elliptic
integral of the first kind (scipy.special.ellipk takes m = k^2); the
small-angle period is T0 = 2 pi sqrt(L/g).
"""

import math

import numpy as np
import opensim as osim
from scipy.special import ellipk

L = 1.0
G = 9.80665
MASS = 1.0
END = 10.0
REPORT = 0.001


def build() -> osim.Model:
    model = osim.Model()
    model.setName("pendulum")
    model.setGravity(osim.Vec3(0.0, -G, 0.0))
    body = osim.Body("bob", MASS, osim.Vec3(0.0), osim.Inertia(0.0, 0.0, 0.0))
    model.addBody(body)
    joint = osim.PinJoint(
        "pin",
        model.getGround(),
        osim.Vec3(0.0),
        osim.Vec3(0.0),
        body,
        osim.Vec3(0.0, L, 0.0),
        osim.Vec3(0.0),
    )
    model.addJoint(joint)
    model.finalizeConnections()
    return model


def simulate(theta0_deg: float) -> tuple[np.ndarray, np.ndarray]:
    model = build()
    state = model.initSystem()
    coord = model.getCoordinateSet().get(0)
    coord.setValue(state, math.radians(theta0_deg))
    coord.setSpeedValue(state, 0.0)
    manager = osim.Manager(model)
    manager.setIntegratorAccuracy(1e-10)
    state.setTime(0.0)
    manager.initialize(state)
    times, angles = [], []
    t = 0.0
    while t < END - 1e-12:
        t = min(END, t + REPORT)
        state = manager.integrate(t)
        times.append(state.getTime())
        angles.append(coord.getValue(state))
    return np.array(times), np.array(angles)


def period(times: np.ndarray, angles: np.ndarray) -> float:
    s = np.sign(angles)
    idx = np.where(s[:-1] * s[1:] < 0)[0]
    crossings = times[idx] - angles[idx] * (times[idx + 1] - times[idx]) / (
        angles[idx + 1] - angles[idx]
    )
    return 2.0 * float(np.mean(np.diff(crossings)))


def main() -> None:
    osim.Logger.setLevelString("warn")  # one info block per integrate() call otherwise
    osim.Logger.removeFileSink()  # do not write opensim.log into the working folder
    print(
        f"opensim {osim.GetVersion()}, L={L} m, g={G} m/s^2, "
        f"integrator accuracy 1e-10, samples every {REPORT} s for {END} s"
    )
    t0 = 2 * math.pi * math.sqrt(L / G)
    print(f"small-angle period 2 pi sqrt(L/g) = {t0:.6f} s")
    print(
        "theta0 (deg), OpenSim period (s), exact period (s), relative error, "
        "max |energy drift| / initial potential energy"
    )
    for theta0 in (10.0, 90.0):
        times, angles = simulate(theta0)
        k = math.sin(math.radians(theta0) / 2)
        exact = 4 * math.sqrt(L / G) * float(ellipk(k * k))
        found = period(times, angles)
        # energy per unit mass from the recorded angle and its finite-difference
        # speed (a check of the recording only, not part of the solution)
        speed = np.gradient(angles, times)
        energy = 0.5 * (L * speed) ** 2 + G * L * (1 - np.cos(angles))
        e0 = G * L * (1 - math.cos(math.radians(theta0)))
        drift = float(np.max(np.abs(energy[5:-5] - e0)) / e0)
        print(f"{theta0:.0f}, {found:.6f}, {exact:.6f}, {(found - exact) / exact:.2e}, {drift:.2e}")


if __name__ == "__main__":
    main()
