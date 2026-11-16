"""Spec 5 research trial: Crawford's unit learning curve against a published table.

Install and run (standard library only):

    python3 -I learning_curve.py > output.txt

Unit theory (Crawford 1947): T_x = T_1 * x**b, b = ln(slope) / ln(2).
Published values: G. K. Mislick (Naval Postgraduate School), "Cost Estimation,
Chapter 10, Learning Curves: Unit Theory", ICEAA 2016 Bristol training TRN 03,
slide "80% Learning Rate Example": T_1 = 1000, 80 % slope, Crawford unit
values (rounded to whole numbers in the slide) for selected units.
"""

import math

PUBLISHED = {
    1: 1000,
    2: 800,
    3: 702,
    4: 640,
    5: 596,
    10: 477,
    50: 284,
    100: 227,
    500: 135,
    1000: 108,
}


def main() -> None:
    b = math.log(0.8) / math.log(2.0)
    print(f"b = ln(0.8)/ln(2) = {b:.4f} (slide: -.3219)")
    print("unit, computed, published (rounded), match after rounding")
    for unit, pub in PUBLISHED.items():
        t = 1000.0 * unit**b
        print(f"{unit}, {t:.2f}, {pub}, {round(t) == pub}")


if __name__ == "__main__":
    main()
