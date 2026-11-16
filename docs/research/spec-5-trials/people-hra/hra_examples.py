"""Spec 5 research trial: HEART and SPAR-H formulas against published examples.

Install and run (standard library only):

    python3 -I hra_examples.py > output.txt

SPAR-H (Gertman et al., NUREG/CR-6883, INL/EXT-05-00509, US NRC, August
2005, section 2.5): composite PSF = product of the PSF multipliers; when
three or more PSFs are negative the adjusted HEP is

    HEP = NHEP * PSFc / (NHEP * (PSFc - 1) + 1),

NHEP = 0.01 for diagnosis, 0.001 for action. Examples 1 and 2 of section
2.5.1 print HEP = 0.81 and HEP = 6.41E-5.

HEART (Williams 1985/1986): HEP = GTT nominal unreliability times, for each
error producing condition (EPC), ((max effect - 1) * assessed proportion + 1).
The example here is the one on the English Wikipedia page "Human error
assessment and reduction technique" (read 2026-11-16), a secondary source:
GTT F, 0.003; EPCs 3 x 0.4, 6 x 1.0, 4 x 0.8, 2.5 x 0.8, 1.2 x 0.6;
printed result 0.27. The page prints each assessed effect (1.8, 6.0, 3.4,
2.2, 1.12); this script computes the effects from the formula and also
multiplies the printed ones.
"""


def spar_h(nhep: float, psfs: list[float], adjust: bool) -> float:
    composite = 1.0
    for p in psfs:
        composite *= p
    if adjust:
        return nhep * composite / (nhep * (composite - 1.0) + 1.0)
    return nhep * composite


def heart(nominal: float, epcs: list[tuple[float, float]], round_to: int | None) -> float:
    hep = nominal
    for max_effect, proportion in epcs:
        effect = (max_effect - 1.0) * proportion + 1.0
        hep *= round(effect, round_to) if round_to is not None else effect
    return hep


def main() -> None:
    print("SPAR-H, NUREG/CR-6883 section 2.5.1")
    ex1 = spar_h(0.01, [10.0, 20.0, 2.0], adjust=True)
    ex1_raw = spar_h(0.01, [10.0, 20.0, 2.0], adjust=False)
    print(
        f"example 1 (diagnosis, PSFs 10, 20, 2): unadjusted {ex1_raw:.4f} "
        f"(report: 4.0), adjusted {ex1:.4f} (report: 0.81)"
    )
    ex2 = spar_h(0.001, [0.8, 0.8, 0.1], adjust=True)
    ex2_raw = spar_h(0.001, [0.8, 0.8, 0.1], adjust=False)
    print(
        f"example 2 (action, PSFs 0.8, 0.8, 0.1): unadjusted {ex2_raw:.3e} "
        f"(report: 6.4E-5), adjusted {ex2:.4e} (report: 6.41E-5)"
    )
    print("HEART, Wikipedia example (secondary source)")
    epcs = [(3.0, 0.4), (6.0, 1.0), (4.0, 0.8), (2.5, 0.8), (1.2, 0.6)]
    print(f"effects from the formula: {heart(0.003, epcs, None):.4f} (page: 0.27)")
    print(f"printed effects multiplied: {0.003 * 1.8 * 6.0 * 3.4 * 2.2 * 1.12:.4f} (page: 0.27)")


if __name__ == "__main__":
    main()
