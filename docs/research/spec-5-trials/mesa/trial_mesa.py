"""Spec 5 trial: Mesa runs an agent-based SIR epidemic in a well-mixed population.

Install (scratch venv, outside the repository):
    uv venv -p 3.12 mesa && VIRTUAL_ENV=$PWD/mesa uv pip install mesa==3.5.2 scipy
Run (from this folder):
    <venv>/bin/python trial_mesa.py > output.txt

Each person is an agent. In each step of dt days, a susceptible agent is infected with
probability 1 - exp(-beta I / N dt) and an infected agent recovers with probability
1 - exp(-gamma dt), decided from the counts at the start of the step (two phases, so the
order of agents does not matter). Randomness comes only from Mesa's seeded generator.
Known answer, for large N: the deterministic SIR final-size relation
S_inf = S0 exp(-R0 (N - S_inf) / N), here N = 1000, I0 = 10, beta = 0.5/day,
gamma = 0.25/day, R0 = 2 (I0 = 10 makes early extinction rare: about (1/R0)^10).
A stochastic model of finite N is not expected to equal it exactly; the trial reports
the mean over replications with a 95% interval, and the spread.
"""

import math
import statistics

import mesa
import numpy as np
from scipy.optimize import brentq

N, I0, BETA, GAMMA, DT, DAYS, REPS = 1000, 10, 0.5, 0.25, 0.1, 200, 30


class Person(mesa.Agent):
    def __init__(self, model: "Epidemic", state: str) -> None:
        super().__init__(model)
        self.state = state
        self.next_state = state

    def decide(self) -> None:
        m = self.model
        if self.state == "S" and m.rng.random() < m.p_infect:
            self.next_state = "I"
        elif self.state == "I" and m.rng.random() < m.p_recover:
            self.next_state = "R"

    def apply(self) -> None:
        self.state = self.next_state


class Epidemic(mesa.Model):
    def __init__(self, seed: int) -> None:
        super().__init__(rng=seed)
        for i in range(N):
            Person(self, "I" if i < I0 else "S")
        self.p_recover = 1 - math.exp(-GAMMA * DT)
        self.p_infect = 0.0

    def count(self, state: str) -> int:
        return sum(1 for a in self.agents if a.state == state)

    def step(self) -> None:
        self.p_infect = 1 - math.exp(-BETA * self.count("I") / N * DT)
        self.agents.do("decide")
        self.agents.do("apply")


def main() -> None:
    print("mesa", mesa.__version__, "numpy", np.__version__)
    s0, r0 = N - I0, BETA / GAMMA
    s_inf = brentq(lambda s: s - s0 * math.exp(-r0 * (N - s) / N), 1e-9, N / r0)
    print(
        f"deterministic final size (N - S_inf): {N - s_inf:.4f} "
        f"(of which {N - s0} infected at the start)"
    )
    sizes = []
    for rep in range(REPS):
        model = Epidemic(seed=12345 + rep)
        for _ in range(int(DAYS / DT)):
            model.step()
            if model.count("I") == 0:
                break
        sizes.append(N - model.count("S"))
    mean, sd = statistics.mean(sizes), statistics.stdev(sizes)
    hw = 2.045 * sd / math.sqrt(REPS)  # t(0.975, 29)
    print(
        f"{REPS} replications, dt {DT} day: mean final size {mean:.2f} +/- {hw:.2f} "
        f"(95%), sd {sd:.2f}, min {min(sizes)}, max {max(sizes)}"
    )
    print(
        "repeat of replication 0 with the same seed equal:",
        sizes[0]
        == (lambda m: ([m.step() for _ in range(int(DAYS / DT))], N - m.count("S"))[1])(
            Epidemic(12345)
        ),
    )


if __name__ == "__main__":
    main()
