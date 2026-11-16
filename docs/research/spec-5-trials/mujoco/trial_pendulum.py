"""Spec 5 trial: MuJoCo (a candidate multibody engine) on the pendulum benchmark.

Project Chrono could not be installed in the research container (conda only), so this
tries MuJoCo, which is on PyPI, as the alternative docs/research/spec-5-chrono.md names.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 mujoco && VIRTUAL_ENV=$PWD/mujoco uv pip install mujoco==4.0.1 scipy
Run (from this folder):
    <venv>/bin/python trial_pendulum.py > output.txt

A point mass of 1 kg on a massless rod of L = 1 m (a body whose inertia about its own
centre is negligible), a hinge with no damping, g = 9.80665 m/s^2, released at rest.
The period is measured from successive upward zero crossings of the angle, linearly
interpolated, averaged over 10 periods. Known answer: T = 4 sqrt(L/g) K(sin(theta0/2)).
"""

import math

import mujoco
import numpy as np
from scipy.special import ellipk

XML = """
<mujoco>
  <option gravity="0 0 -9.80665" timestep="{dt}" integrator="{integrator}"/>
  <worldbody>
    <body name="bob" pos="0 0 0">
      <joint name="hinge" type="hinge" axis="0 1 0" damping="0" armature="0"/>
      <inertial pos="0 0 -1" mass="1" diaginertia="1e-12 1e-12 1e-12"/>
    </body>
  </worldbody>
</mujoco>
"""


def period(degrees: float, dt: float, integrator: str) -> float:
    model = mujoco.MjModel.from_xml_string(XML.format(dt=dt, integrator=integrator))
    data = mujoco.MjData(model)
    data.qpos[0] = math.radians(degrees)
    crossings = []
    previous = data.qpos[0]
    while len(crossings) < 11:
        t0 = data.time
        mujoco.mj_step(model, data)
        q = data.qpos[0]
        if previous < 0 <= q:
            crossings.append(t0 + dt * (-previous) / (q - previous))
        previous = q
    return (crossings[-1] - crossings[0]) / 10


def main() -> None:
    print("mujoco", mujoco.__version__, "numpy", np.__version__)
    length, g = 1.0, 9.80665
    for degrees in (10, 90):
        exact = 4 * math.sqrt(length / g) * ellipk(math.sin(math.radians(degrees) / 2) ** 2)
        for integrator, dt in (("RK4", 1e-3), ("RK4", 1e-4), ("Euler", 1e-4)):
            t = period(degrees, dt, integrator)
            print(
                f"{degrees:>2} deg, {integrator:<5} dt {dt:g} s: T {t:.9f} s, "
                f"exact {exact:.9f} s, relative error {(t - exact) / exact:+.2e}"
            )


if __name__ == "__main__":
    main()
