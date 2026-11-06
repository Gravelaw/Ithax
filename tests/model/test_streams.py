"""Random streams (spec 1 "Random streams"; AKS-96).

The stream key is the UTF-8 string ``<seed>:<replication>:<component id>``; its SHA-256
digest, read as a big-endian integer, seeds ``numpy.random.SeedSequence``, which seeds a
PCG64 ``numpy.random.Generator``. These tests check the key, the construction, that two
processes agree, that one component's stream does not depend on the others, the reserved
``optimizer`` key of spec 2, and the generator name and numpy version for the manifest.
"""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy
import pytest

from lcsim.model.loading import build_document
from lcsim.model.model import Model
from lcsim.model.streams import (
    GENERATOR_NAME,
    MAX_SEED,
    OPTIMIZER_STREAM,
    GeneratorInfo,
    generator_for,
    generator_info,
    optimizer_generator,
    stream_key,
    streams_for,
)

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)

# The first three raw 64-bit outputs of the PCG64 stream for key "12345:0:till", observed
# with numpy 2.5.4 on Python 3.13 and pinned so that a change to the scheme is caught. A
# bit generator's raw output is kept stable across numpy versions (NEP 19); CI checks it on
# numpy 2.4.6 (Python 3.11) as well.
TILL_RAW = [16180610253307400644, 153601319691555175, 4906584438583461370]


def model_of(document: dict[str, Any]) -> Model:
    result = build_document(document, seed_source=lambda: 7)
    assert result.issues == (), [issue.as_dict() for issue in result.issues]
    assert result.model is not None
    return result.model


def test_the_key_is_seed_replication_and_component_id() -> None:
    assert stream_key(12345, 0, "till") == "12345:0:till"
    assert stream_key(0, 29, "arrivals") == "0:29:arrivals"
    assert stream_key(MAX_SEED, 1, "exit") == f"{2**63 - 1}:1:exit"


def test_the_generator_is_pcg64_seeded_by_the_sha256_of_the_key() -> None:
    entropy = int.from_bytes(hashlib.sha256(b"12345:0:till").digest(), "big")
    expected = numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence(entropy)))
    rng = generator_for(12345, 0, "till")
    assert isinstance(rng.bit_generator, numpy.random.PCG64)
    assert rng.bit_generator.state == expected.bit_generator.state
    assert rng.random(5).tolist() == expected.random(5).tolist()


def test_the_key_is_encoded_as_utf8() -> None:
    entropy = int.from_bytes(hashlib.sha256("1:0:café".encode()).digest(), "big")
    expected = numpy.random.PCG64(numpy.random.SeedSequence(entropy))
    assert generator_for(1, 0, "café").bit_generator.state == expected.state


def test_the_stream_is_pinned() -> None:
    assert generator_for(12345, 0, "till").bit_generator.random_raw(3).tolist() == TILL_RAW


def test_the_same_key_gives_the_same_stream() -> None:
    first = generator_for(42, 3, "till").random(100)
    second = generator_for(42, 3, "till").random(100)
    assert first.tolist() == second.tolist()


@pytest.mark.parametrize(
    ("seed", "replication", "component_id"),
    [(12346, 0, "till"), (12345, 1, "till"), (12345, 0, "arrivals")],
)
def test_a_different_seed_replication_or_component_gives_another_stream(
    seed: int, replication: int, component_id: str
) -> None:
    base = generator_for(12345, 0, "till").random(10).tolist()
    assert generator_for(seed, replication, component_id).random(10).tolist() != base


_CHILD = """
import json, sys
from lcsim.model.streams import generator_for
rng = generator_for(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
print(json.dumps(rng.random(50).tolist()))
"""


@pytest.mark.parametrize("hash_seed", ["0", "1", "random"])
def test_two_processes_give_the_same_stream(hash_seed: str) -> None:
    """Spec 1: ``hash()`` is salted per process and is never used; a separately started
    interpreter, with any hash seed, draws the same numbers for the same key."""
    environment = dict(os.environ, PYTHONHASHSEED=hash_seed)
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD, "12345", "2", "till"],
        capture_output=True,
        check=True,
        env=environment,
        text=True,
    )
    assert json.loads(completed.stdout) == generator_for(12345, 2, "till").random(50).tolist()


def test_adding_or_removing_a_component_leaves_other_streams_unchanged() -> None:
    """Spec 1: "Adding or removing one component therefore leaves every other component's
    random numbers unchanged." The coffee shop gains a delay between till and exit."""
    base = model_of(copy.deepcopy(COFFEE_SHOP))
    grown_document = copy.deepcopy(COFFEE_SHOP)
    grown_document["components"].insert(
        2,
        {
            "id": "walk",
            "type": "delay",
            "params": {"time": {"dist": "uniform", "min": "10 s", "max": "30 s"}},
        },
    )
    grown_document["connections"] = [
        {"from": "arrivals.out", "to": "till.in"},
        {"from": "till.out", "to": "walk.in"},
        {"from": "walk.out", "to": "exit.in"},
    ]
    grown = model_of(grown_document)
    seed = base.experiments[0].seed
    before = streams_for(seed, 4, [component.id for component in base.components])
    after = streams_for(seed, 4, [component.id for component in grown.components])
    assert list(before) == ["arrivals", "till", "exit"]
    assert list(after) == ["arrivals", "till", "walk", "exit"]
    for component_id, rng in before.items():
        assert rng.random(20).tolist() == after[component_id].random(20).tolist()


def test_streams_for_gives_each_component_its_own_generator() -> None:
    streams = streams_for(12345, 0, ["arrivals", "till"])
    assert streams["arrivals"] is not streams["till"]
    assert streams["till"].random(5).tolist() == generator_for(12345, 0, "till").random(5).tolist()


def test_streams_for_refuses_a_repeated_component_id() -> None:
    with pytest.raises(ValueError, match="'till' more than once"):
        streams_for(1, 0, ["till", "till"])


def test_the_reserved_optimizer_stream_is_replication_zero() -> None:
    """Spec 2 "Simulation-based optimization": the search is seeded from the stream key
    ``<seed>:0:optimizer``; ``optimizer`` is a reserved identifier (E112)."""
    assert OPTIMIZER_STREAM == "optimizer"
    assert stream_key(12345, 0, OPTIMIZER_STREAM) == "12345:0:optimizer"
    expected = generator_for(12345, 0, "optimizer").random(10).tolist()
    assert optimizer_generator(12345).random(10).tolist() == expected
    assert optimizer_generator(12345).random(10).tolist() != (
        generator_for(12345, 1, "optimizer").random(10).tolist()
    )


def test_generator_info_for_the_manifest() -> None:
    """Spec 1 "Run folder and results": ``generator {name, numpy_version}``."""
    info = generator_info()
    assert info == GeneratorInfo(name="PCG64", numpy_version=numpy.__version__)
    assert GENERATOR_NAME == type(generator_for(1, 0, "a").bit_generator).__name__
    assert info.as_dict() == {"name": "PCG64", "numpy_version": numpy.__version__}


@pytest.mark.parametrize("seed", [-1, 2**63, True, 1.0, "1"])
def test_a_seed_outside_the_spec_range_is_refused(seed: Any) -> None:
    """Spec 1 "Experiments": a seed is a whole number from 0 to 2⁶³ - 1."""
    with pytest.raises(ValueError, match="seed"):
        stream_key(seed, 0, "till")


@pytest.mark.parametrize("replication", [-1, True, 1.0])
def test_a_replication_that_is_not_a_count_from_zero_is_refused(replication: Any) -> None:
    with pytest.raises(ValueError, match="replication"):
        stream_key(1, replication, "till")


def test_an_empty_component_id_is_refused() -> None:
    with pytest.raises(ValueError, match="component id"):
        stream_key(1, 0, "")
