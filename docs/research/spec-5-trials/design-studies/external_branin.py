"""A stand-in file-exchanging engine: reads a JSON object {"x1": .., "x2": ..} from argv[1],
writes {"f": ..} to argv[2]. f is the Branin function (sfu.ca/~ssurjano/branin.html).
Usage: python external_branin.py input.json output.json
"""

import json
import math
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    values = json.load(handle)
x1, x2 = float(values["x1"]), float(values["x2"])
b, c, t = 5.1 / (4 * math.pi**2), 5 / math.pi, 1 / (8 * math.pi)
f = (x2 - b * x1**2 + c * x1 - 6) ** 2 + 10 * (1 - t) * math.cos(x1) + 10
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump({"f": f}, handle)
