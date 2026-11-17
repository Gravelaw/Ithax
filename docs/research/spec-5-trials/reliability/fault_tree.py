"""Trial 3: a small fault tree (AND, OR, 2-out-of-3 vote) in three libraries.

Structure: the safety instrumented function of Lundteigen and Rausand, SIS book
ch. 5 slides 8-10 (read 2026-11-16): TOP = PT voted 2oo3 fails OR LS fails OR
(SDV1 AND SDV2 fail). Published minimal cut sets: {PT1,PT2}, {PT1,PT3},
{PT2,PT3}, {LS}, {SDV1,SDV2}. Basic event probabilities are chosen here.

Known answers (closed form, by hand):
- exact: Q = 1 - (1 - Q_PT)(1 - q_LS)(1 - q_SDV^2), Q_PT = 3q^2 - 2q^3
  (Rausand ch. 4 slide 14 for 2oo3; NIST 8.1.8.2 for series).
- rare-event approximation: sum of cut-set probabilities.
- minimal cut set upper bound: 1 - prod(1 - Q_j) (Lundteigen and Rausand slide 14).
- an independent check: sum over all 2^6 basic-event states (truth table).

Install (scratch venv, Python 3.12, Linux):
    VIRTUAL_ENV=venv uv pip install repyability==0.19.1 faultree==0.4.0 pfta==0.4.0
Run:
    venv/bin/python fault_tree.py > output-fault_tree.txt
pfta (GPL-3.0-only) is run as a separate process through its command line, as
an Ithax adapter would; its output goes to a temporary folder.
"""

import csv
import itertools
import subprocess
import sys
import tempfile
from importlib.metadata import version
from math import prod
from pathlib import Path

Q = {"PT1": 0.05, "PT2": 0.05, "PT3": 0.05, "LS": 0.01, "SDV1": 0.10, "SDV2": 0.10}
CUT_SETS = [{"PT1", "PT2"}, {"PT1", "PT3"}, {"PT2", "PT3"}, {"LS"}, {"SDV1", "SDV2"}]


def top(failed: set[str]) -> bool:
    pt = sum(e in failed for e in ("PT1", "PT2", "PT3")) >= 2
    return pt or "LS" in failed or {"SDV1", "SDV2"} <= failed


def truth_table() -> float:
    names = list(Q)
    total = 0.0
    for states in itertools.product([False, True], repeat=len(names)):
        failed = {n for n, s in zip(names, states, strict=True) if s}
        if top(failed):
            total += prod(Q[n] if s else 1 - Q[n] for n, s in zip(names, states, strict=True))
    return total


def closed_forms() -> dict[str, float]:
    q = Q["PT1"]
    q_pt = 3 * q**2 - 2 * q**3
    cut_q = [prod(Q[e] for e in c) for c in CUT_SETS]
    return {
        "exact (closed form)": 1 - (1 - q_pt) * (1 - Q["LS"]) * (1 - Q["SDV1"] * Q["SDV2"]),
        "exact (truth table, 64 states)": truth_table(),
        "rare-event approximation": sum(cut_q),
        "min cut set upper bound": 1 - prod(1 - x for x in cut_q),
    }


def with_repyability() -> tuple[float, list[list[str]]]:
    import repyability as rp

    gates = {
        "TOP": ("or", ["G_PT", "LS", "G_SDV"]),
        "G_PT": ("vote", 2, ["PT1", "PT2", "PT3"]),
        "G_SDV": ("and", ["SDV1", "SDV2"]),
    }
    ft = rp.FaultTree(gates, dict(Q))
    return float(ft.top_event_probability()), sorted(sorted(c) for c in ft.minimal_cut_sets())


def with_faultree() -> tuple[float, list[list[str]]]:
    import faultree

    tree = {
        "id": "TOP",
        "gate": "OR",
        "children": [
            {
                "id": "G_PT",
                "gate": "K_OF_N",
                "k": 2,
                "children": [{"id": n, "prob": Q[n]} for n in ("PT1", "PT2", "PT3")],
            },
            {"id": "LS", "prob": Q["LS"]},
            {
                "id": "G_SDV",
                "gate": "AND",
                "children": [{"id": n, "prob": Q[n]} for n in ("SDV1", "SDV2")],
            },
        ],
    }
    result = faultree.analyze(tree)
    mcs = faultree.minimal_cut_sets(tree)
    return float(result["Q"]), mcs


PFTA_TEXT = """- times: 1
- time_unit: h

Gate: TOP
- type: OR
- inputs: G_PT, LS, G_SDV

Gate: G_PT
- type: VOTE(2)
- inputs: PT1, PT2, PT3

Gate: G_SDV
- type: AND
- inputs: SDV1, SDV2
"""


def with_pfta() -> tuple[float, list[str]]:
    text = PFTA_TEXT + "".join(
        f"\nEvent: {n}\n- model_type: Fixed\n- probability: {q}\n- intensity: 0\n"
        for n, q in Q.items()
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sif.txt"
        path.write_text(text)
        exe = Path(sys.executable).parent / "pfta"
        proc = subprocess.run([str(exe), str(path)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stdout + proc.stderr)
        out = Path(tmp) / "sif.txt.out"
        with open(out / "gates.tsv", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        top_row = next(r for r in rows if r["id"] == "TOP")
        with open(out / "cut-sets" / "TOP.tsv", newline="") as fh:
            cut_rows = [r["cut_set"] for r in csv.DictReader(fh, delimiter="\t")]
        print(
            "  pfta output files: "
            + str(sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()))
        )
        print(f"  pfta TOP row: {top_row}")
        return float(top_row["computed_probability"]), sorted(cut_rows)


def main() -> None:
    print(f"basic events: {Q}")
    print(f"published minimal cut sets: {sorted(sorted(c) for c in CUT_SETS)}")
    known = closed_forms()
    for k, v in known.items():
        print(f"{k:<34} Q = {v:.12f}")
    exact = known["exact (closed form)"]
    for name, fn in (
        ("repyability " + version("repyability"), with_repyability),
        ("faultree " + version("faultree"), with_faultree),
        ("pfta " + version("pfta") + " (subprocess)", with_pfta),
    ):
        try:
            q, mcs = fn()
            print(f"{name:<34} Q = {q:.12f} diff vs exact {q - exact:+.1e}")
            print(f"  cut sets: {mcs}")
        except Exception as exc:  # research script: report and continue
            print(f"{name}: FAILED {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
