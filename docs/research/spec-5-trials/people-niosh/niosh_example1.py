"""Spec 5 research trial: the revised NIOSH lifting equation against the
published worked example 1 ("Loading Punch Press Stock") of the NIOSH
Applications Manual (NIOSH [1994], revised September 2021, DHHS (NIOSH)
Publication 94-110, doi:10.26616/NIOSHPUB94110revised092021, section 3.2.1).

Install and run (standard library only):

    python3 -I niosh_example1.py > output.txt

RWL = LC * HM * VM * DM * AM * FM * CM (US customary units, manual section 1.3):
LC = 51 lb, HM = 10/H, VM = 1 - 0.0075 |V - 30|, DM = 0.82 + 1.8/D,
AM = 1 - 0.0032 A, FM from Table 5, CM from Table 7. LI = load / RWL.

The manual's worksheets use the multipliers as read from its Tables 1 to 7,
rounded to two decimals. This script computes each case twice: with the
formulas unrounded, and with each multiplier rounded to two decimals (for
H = 23 in, Table 1 prints .44 while 10/23 = 0.4348).
"""

LC = 51.0


def multipliers(h: float, v: float, d: float, a: float, fm: float, cm: float) -> list[float]:
    return [10.0 / h, 1 - 0.0075 * abs(v - 30.0), 0.82 + 1.8 / d, 1 - 0.0032 * a, fm, cm]


def rwl(ms: list[float]) -> float:
    out = LC
    for m in ms:
        out *= m
    return out


TABLE_HM = {10.0: 1.00, 12.0: 0.83, 23.0: 0.44}  # Table 1 rows used

# (case, H in, V in, D in, A deg, FM, CM, published RWL lb, published LI)
CASES = [
    ("example 1, origin", 23.0, 15.0, 48.0, 0.0, 1.00, 0.95, 16.3, 2.7),
    ("example 1, destination", 23.0, 63.0, 48.0, 0.0, 1.00, 1.00, 14.5, 3.0),
    ("modified example 1, origin", 10.0, 15.0, 48.0, 0.0, 1.00, 0.90, 35.1, 1.3),
    ("modified example 1, destination", 12.0, 63.0, 48.0, 0.0, 1.00, 0.90, 24.6, 1.8),
]
LOAD = 44.0


def main() -> None:
    print(
        "case, RWL formula (lb), RWL table-rounded (lb), published RWL, "
        "LI table-rounded, published LI"
    )
    for name, h, v, d, a, fm, cm, pub_rwl, pub_li in CASES:
        exact = multipliers(h, v, d, a, fm, cm)
        rounded = [round(m, 2) for m in exact]
        rounded[0] = TABLE_HM[h]
        r_exact, r_table = rwl(exact), rwl(rounded)
        print(f"{name}, {r_exact:.2f}, {r_table:.2f}, {pub_rwl}, {LOAD / r_table:.2f}, {pub_li}")


if __name__ == "__main__":
    main()
