"""Spec 5 research trial: N people leave a room through one door in JuPedSim.

Install and run (research code, not product code):

    uv venv -p 3.12 venv
    VIRTUAL_ENV=venv uv pip install jupedsim==1.4.2
    venv/bin/python -I room_exit.py > output.txt

Geometry: a 10 m x 10 m room (x 0..10, y 0..10) with a door of width b in the
wall x = 10, centred at y = 5, opening into a 4 m long corridor of the same
width, whose far end is the exit stage. Agents start in the room at a fixed
seed. The engine's own model (collision-free speed model, Tordeux et al.,
default parameters, and once with the agents' time_gap set to 0.5 s instead
of the default 1 s; and the generalized centrifugal force model)
moves them; this script only counts when each agent
crosses the door line x = 10 and computes

    specific flow J_s = (n - 1) / (t_last - t_first) / b

over the crossings from the 10th to the (N - 10)th agent (the steady part),
for comparison with published bottleneck flows (see the research note).
A run stops at 600 s of simulated time if agents remain (a jam); an engine
error is printed and the next case runs.
"""

import time

import jupedsim as jps
import numpy as np
import shapely

ROOM = 10.0
CORRIDOR = 4.0
N = 150
DT = 0.01
SEED = 1


def geometry(b: float) -> shapely.Polygon:
    room = shapely.box(0.0, 0.0, ROOM, ROOM)
    corridor = shapely.box(ROOM, 5.0 - b / 2, ROOM + CORRIDOR, 5.0 + b / 2)
    return shapely.union(room, corridor)


def run(b: float, model_name: str, time_gap: float = 1.0) -> dict[str, float]:
    model = (
        jps.CollisionFreeSpeedModel()
        if model_name == "CollisionFreeSpeedModel"
        else jps.GeneralizedCentrifugalForceModel()
    )
    sim = jps.Simulation(model=model, geometry=geometry(b), dt=DT)
    exit_id = sim.add_exit_stage(
        shapely.box(ROOM + CORRIDOR - 0.5, 5.0 - b / 2, ROOM + CORRIDOR, 5.0 + b / 2)
    )
    journey_id = sim.add_journey(jps.JourneyDescription([exit_id]))
    start_area = shapely.box(0.5, 0.5, 8.0, 9.5)
    positions = jps.distribute_by_number(
        polygon=start_area,
        number_of_agents=N,
        distance_to_agents=0.45,
        distance_to_polygon=0.3,
        seed=SEED,
    )
    for pos in positions:
        if model_name == "CollisionFreeSpeedModel":
            params = jps.CollisionFreeSpeedModelAgentParameters(
                position=pos, journey_id=journey_id, stage_id=exit_id, time_gap=time_gap
            )
        else:
            params = jps.GeneralizedCentrifugalForceModelAgentParameters(
                position=pos, journey_id=journey_id, stage_id=exit_id
            )
        sim.add_agent(params)
    crossed: dict[int, float] = {}
    wall = time.perf_counter()
    while sim.agent_count() > 0 and sim.elapsed_time() < 600.0:
        sim.iterate()
        for agent in sim.agents():
            if agent.id not in crossed and agent.position[0] >= ROOM:
                crossed[agent.id] = sim.elapsed_time()
    wall = time.perf_counter() - wall
    times = np.sort(np.array(list(crossed.values())))
    steady = times[10 : N - 10]
    flow = (len(steady) - 1) / (steady[-1] - steady[0]) if len(steady) > 1 else float("nan")
    return {
        "b": b,
        "crossed": float(len(times)),
        "left_in_sim": float(sim.agent_count()),
        "evac_time": sim.elapsed_time(),
        "flow": flow,
        "specific_flow": flow / b,
        "wall_s": wall,
    }


def main() -> None:
    print(f"jupedsim {jps.__version__}, N={N}, dt={DT} s, seed={SEED}")
    print(
        "model, door width b (m), crossed, left, evacuation time (s), "
        "flow (1/s), specific flow (1/(m s)), wall time (s)"
    )
    cases = [
        ("CollisionFreeSpeedModel", 1.0),
        ("CollisionFreeSpeedModel", 0.5),
        ("GeneralizedCentrifugalForceModel", 1.0),
    ]
    for model_name, time_gap in cases:
        label = model_name + (f" time_gap={time_gap}" if "Collision" in model_name else "")
        for b in (0.8, 1.0, 1.2, 1.6, 2.0):
            try:
                r = run(b, model_name, time_gap)
            except RuntimeError as err:
                print(f"{label}, {b:.1f}, engine error: {err}")
                continue
            print(
                f"{label}, {r['b']:.1f}, {r['crossed']:.0f}, "
                f"{r['left_in_sim']:.0f}, {r['evac_time']:.2f}, {r['flow']:.3f}, "
                f"{r['specific_flow']:.3f}, {r['wall_s']:.1f}"
            )


if __name__ == "__main__":
    main()
