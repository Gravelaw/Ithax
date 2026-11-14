"""Random streams (spec 1 "Random streams").

Each component gets its own random stream in each replication. The stream key is the
UTF-8 string ``<seed>:<replication>:<component id>`` (replication numbered from 0). Its
SHA-256 digest, read as a big-endian integer, seeds ``numpy.random.SeedSequence``, which
seeds a PCG64 ``numpy.random.Generator``. Python's ``hash()`` is salted per process and is
never used, nor is the global random generator (guide "Conventions", Randomness): every
random number lcsim draws comes from a generator made here.

Scenario and search candidate do not enter the key (common random numbers), and a
component's stream depends on its own id only, so adding or removing a component leaves
every other component's stream unchanged. The simulation-based search of spec 2 draws from
the reserved key ``<seed>:0:optimizer``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

import numpy

from ithax.strict_json import is_whole

__all__ = [
    "GENERATOR_NAME",
    "MAX_SEED",
    "OPTIMIZER_STREAM",
    "GeneratorInfo",
    "generator_for",
    "generator_info",
    "optimizer_generator",
    "stream_key",
    "streams_for",
]

# The bit generator's name, as ``manifest.json`` records it (spec 1 "Run folder and
# results": ``generator {name, numpy_version}``).
GENERATOR_NAME = "PCG64"

# Spec 1 "Experiments": a seed runs from 0 to 2⁶³ - 1.
MAX_SEED = 2**63 - 1

# Spec 2 "Simulation-based optimization": the search's stream key is
# ``<seed>:0:optimizer``; ``optimizer`` is a reserved identifier (spec 1, E112).
OPTIMIZER_STREAM = "optimizer"


@dataclass(frozen=True)
class GeneratorInfo:
    """The generator a run used, for ``manifest.json``; a repeat is promised only on the
    same versions (spec 1 "Random streams")."""

    name: str
    numpy_version: str

    def as_dict(self) -> dict[str, str]:
        """The manifest's ``generator`` object, keys in spec order."""
        return {"name": self.name, "numpy_version": self.numpy_version}


def generator_info() -> GeneratorInfo:
    """The generator name and the numpy version in use."""
    return GeneratorInfo(name=GENERATOR_NAME, numpy_version=numpy.__version__)


def stream_key(seed: int, replication: int, component_id: str) -> str:
    """The stream key ``<seed>:<replication>:<component id>``, with the seed and the
    replication as decimal whole numbers.

    A seed outside 0 to 2⁶³ - 1, a replication below 0, a value that is not a whole
    number (``True`` included) and an empty component id are programming errors, since
    loading never gives them: they raise ``ValueError``.
    """
    if not is_whole(seed) or not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed {seed!r} is not a whole number from 0 to 2**63 - 1")
    if not is_whole(replication) or replication < 0:
        raise ValueError(f"replication {replication!r} is not a whole number from 0")
    if not component_id:
        raise ValueError("the component id of a stream key is empty")
    return f"{seed}:{replication}:{component_id}"


def generator_for(seed: int, replication: int, component_id: str) -> numpy.random.Generator:
    """The PCG64 generator of the stream ``<seed>:<replication>:<component id>``."""
    key = stream_key(seed, replication, component_id)
    entropy = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest(), "big")
    return numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence(entropy)))


def streams_for(
    seed: int, replication: int, component_ids: Iterable[str]
) -> dict[str, numpy.random.Generator]:
    """One generator per component of one replication, in the order given. A repeated id
    raises ``ValueError``: two components would share one stream."""
    streams: dict[str, numpy.random.Generator] = {}
    for component_id in component_ids:
        if component_id in streams:
            raise ValueError(f"component id {component_id!r} more than once")
        streams[component_id] = generator_for(seed, replication, component_id)
    return streams


def optimizer_generator(seed: int) -> numpy.random.Generator:
    """The search's generator, from the reserved key ``<seed>:0:optimizer`` (spec 2)."""
    return generator_for(seed, 0, OPTIMIZER_STREAM)
