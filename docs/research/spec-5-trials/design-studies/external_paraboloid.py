"""A stand-in black-box engine: reads input.txt (x and y), writes output.txt (f).

It plays the part of a separate-process engine that exchanges files, as an Ithax adapter
does. f is the OpenMDAO paraboloid, f = (x - 3)^2 + x y + (y + 4)^2 - 3.
Usage: python external_paraboloid.py input.txt output.txt
"""

import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    x, y = (float(part) for part in handle.read().split())
f = (x - 3.0) ** 2 + x * y + (y + 4.0) ** 2 - 3.0
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    handle.write(f"{f!r}\n")
