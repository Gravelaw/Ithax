# Spec 5 research: Mesa for agent-based models

## Question

Spec 5 "New engine adapters" names Mesa for agent-based models, and "Research before building" asks for its current state, licence, upkeep and how it installs under WSL. Is Mesa usable under the spec 1 engine licence rule, how is it driven, and does it reproduce a known answer on a small case?

## Finding

Read on 2026-11-16.

- **Version.** Mesa 3.5.2, uploaded to PyPI on 2026-10-28. A 4.0.0a0 pre-release was uploaded on 2026-03-14, so a major version with API changes is in progress.
- **Licence.** Apache-2.0. Read from `mesa-3.5.2.dist-info/licenses/LICENSE` in the wheel `mesa-3.5.2-py3-none-any.whl` (SHA-256 `ec6dcb7e…e610`, equal to PyPI's digest). `NOTICE` reads "Copyright 2014-2024 Core Mesa Team and contributors". Apache-2.0 is compatible with AGPL-3.0 for a combined work, so Mesa may be imported in-process under the spec 1 rule.
- **Upkeep.** 17 releases on PyPI between 2024-11-16 and 2026-11-16 (PyPI JSON).
- **Python.** `requires_python >=3.12`. Ithax's `pyproject.toml` says `>=3.11`, and the Linux package ships Python 3.13.16 (`scripts/package_linux.py`). Mesa cannot be installed into a Python 3.11 environment.
- **Dependencies** (wheel metadata): numpy, pandas, scipy, tqdm. The visual extras (`viz`, `rec`: solara, altair, matplotlib) are optional and not needed by an adapter.
- **Linux and WSL 2.** A pure-Python wheel (`py3-none-any`). Under WSL 2 it installs with pip as on any Linux. It needs no graphics or system library.
- **Randomness.** `mesa.Model(rng=...)` takes a `numpy.random.Generator` and keeps that object as `model.rng`. `model.random`, a `random.Random` used by `AgentSet.shuffle_do`, is then seeded from it: two models given equal generators drew the same `model.random.random()` (0.5809350744858162 twice). So an adapter can hand Mesa a generator built by spec 1's stream scheme (`<seed>:<replication>:<key>`), and the stream scheme keeps holding.
- **What Mesa is.** A library of `Model`, `Agent`, `AgentSet`, spaces (grids, continuous, networks) and data collection. The model's rules are Python code the user writes. Mesa has no file format for a model.

## Sources

- PyPI JSON, <https://pypi.org/pypi/mesa/json>, read 2026-11-16.
- The wheel `mesa-3.5.2-py3-none-any.whl`: `licenses/LICENSE`, `licenses/NOTICE`, `METADATA`.
- Mesa 3.5.2 source as installed: `mesa/model.py` (`__init__`, `rng` and `random`), `mesa/agent.py` (`AgentSet(..., random=model.random)`).
- Final-size relation of the SIR model: Kermack and McKendrick (1927); in the form used here, Brauer, F. (2008), "Compartmental models in epidemiology", in *Mathematical Epidemiology*, Lecture Notes in Mathematics 1945, Springer, section 2.4.

## Decision

Proposed (owner to confirm):

- **Mesa is the agent-based engine**, pinned below 4.0 until 4.0 is released and tried. It is imported in-process (Apache-2.0); `Capabilities.licence` `Apache-2.0`, `invocation` `in-process`, `distribution` `mesa`.
- **Rules come from a fixed set of component types, not from user code.** Mesa has no model file, so the adapter builds a Mesa model from the Ithax model file. A model file never holds Python code: a project is data, loaded through the strict JSON reader, and spec 4's assistants edit it through the MCP tools. Spec 5 version 0.3 therefore lists agent rules as component types with settings (for example `contact`, `move`, `transition`), each a fixed behaviour with parameters, as spec 2's blocks are.
- **Randomness.** One stream per agent population per replication, keyed `<seed>:<replication>:<component id>` as in spec 1, given to `mesa.Model(rng=...)`.

Open questions:

- **Blocking (a convention):** Mesa needs Python 3.12 or later, and Ithax supports 3.11. Options: (a) the agent-based adapter is installed only on Python 3.12 or later, and on 3.11 its domain is reported as having no engine (E102); (b) Ithax's minimum becomes 3.12. Recommended: (a), since the package already ships 3.13.
- **Reversible:** the agent rule types are a first set chosen by this research, to be checked against the templates M23 writes.

## Tested

`docs/research/spec-5-trials/mesa/trial_mesa.py`, output in `output.txt` beside it. Mesa 3.5.2, numpy 2.5.5, Python 3.12, in a scratch virtual environment outside the repository.

- **Case.** SIR epidemic, every person an agent, well mixed: N = 1000, I0 = 10, β = 0.5 per day, γ = 0.25 per day (R0 = 2), steps of 0.1 day, decisions taken from the counts at the start of each step in two phases.
- **Known answer.** The deterministic final size N − S∞ from S∞ = S0 exp(−R0 (N − S∞)/N): 800.2040.
- **Result.** 30 replications: mean final size 796.03 ± 9.18 (95%), standard deviation 24.59, from 740 to 839. The deterministic value lies inside the interval. A stochastic model of finite N is not expected to equal it exactly, so a benchmark compares with a confidence interval, as spec 2 does.
- **Repeat.** Replication 0 repeated with the same seed gave the same final size (`True`).
- **Time.** 13.6 s for the 30 replications (`time`, 4 cores). Mesa calls Python for every agent at every step, so large populations are slow; spec 5 records this as a performance target to measure, not a promise.
