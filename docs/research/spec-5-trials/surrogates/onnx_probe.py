"""Spec 5 research probe: can skl2onnx export the surrogates trial.py fits?

Research code. Same environment as trial.py:

    VIRTUAL_ENV=venv uv pip install numpy==2.5.4 scipy==1.18.1 scikit-learn==1.9.1 \
        skl2onnx==1.20.0 onnx==1.23.2 onnxruntime==1.32.0
    venv/bin/python -I onnx_probe.py > onnx_probe_output.txt

A toy data set (30 points, 2 inputs, seeded). For each Gaussian process kernel
and for HistGradientBoostingRegressor: convert with skl2onnx, run the ONNX file
with onnxruntime, and compare with scikit-learn's own predictions.
"""

from __future__ import annotations

import warnings

import numpy as np
import onnx
import onnxruntime as ort
import skl2onnx
import sklearn
from skl2onnx import to_onnx
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, Matern

print(
    f"scikit-learn {sklearn.__version__}, skl2onnx {skl2onnx.__version__}, "
    f"onnx {onnx.__version__}, onnxruntime {ort.__version__}"
)
X = np.random.default_rng(0).random((30, 2))
y = np.sin(6 * X[:, 0]) + X[:, 1]


def run(model: object, x: np.ndarray, std: bool) -> list[np.ndarray]:
    opts = {id(model): {"return_std": True}} if std else None
    o = to_onnx(model, x, options=opts)
    s = ort.InferenceSession(o.SerializeToString(), providers=["CPUExecutionProvider"])
    return s.run(None, {s.get_inputs()[0].name: x})


KERNELS = {
    "RBF (one length scale per input)": lambda: ConstantKernel() * RBF([0.5, 0.5]),
    "Matern 5/2 (one length scale)": lambda: ConstantKernel() * Matern(0.5, nu=2.5),
    "Matern 5/2 (one per input)": lambda: ConstantKernel() * Matern([0.5, 0.5], nu=2.5),
}
for kname, kernel in KERNELS.items():
    for norm in (True, False):
        m = GaussianProcessRegressor(kernel(), normalize_y=norm)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(X, y)
        mu, sd = m.predict(X, return_std=True)
        for std in (False, True):
            tag = f"GP {kname}, normalize_y={norm}, {'mean+std' if std else 'mean'}"
            try:
                out = run(m, X, std)
                line = f"converted; mean max |diff| {np.max(np.abs(out[0].ravel() - mu)):.3g}"
                if std:
                    line += f"; std max |diff| {np.max(np.abs(out[1].ravel() - sd)):.3g}"
                    line += f" (sklearn std range {sd.min():.3g} to {sd.max():.3g})"
            except Exception as exc:  # record the converter's failure
                line = f"FAILED {type(exc).__name__}: {str(exc).splitlines()[0][:90]}"
            print(f"{tag}: {line}")

h = HistGradientBoostingRegressor(min_samples_leaf=2, random_state=0).fit(X, y)
for dt in (np.float32, np.float64):
    try:
        out = run(h, X.astype(dt), False)
        print(
            f"HGB {dt.__name__}: converted; "
            f"max |diff| {np.max(np.abs(out[0].ravel() - h.predict(X))):.3g}"
        )
    except Exception as exc:
        cause = exc.__cause__ or exc.__context__
        print(
            f"HGB {dt.__name__}: FAILED {type(exc).__name__}: {str(exc)[:60]}...; "
            f"underlying: {cause!r}"
        )
