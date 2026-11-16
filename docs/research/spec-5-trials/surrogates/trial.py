"""Spec 5 research trial: surrogates of known functions with few runs.

Research code, not product code. It fits surrogates with library calls only
(scikit-learn, SMT, skl2onnx/onnxruntime); it writes no solver of its own.

Install (Python 3.12, a fresh virtual environment outside the repository):

    uv venv -p 3.12 venv
    VIRTUAL_ENV=venv uv pip install numpy==2.5.4 scipy==1.18.1 scikit-learn==1.9.1 \
        smt==2.15.1 skops==0.16.0 skl2onnx==1.20.0 onnx==1.23.2 onnxruntime==1.32.0

Run (846 s measured on four cores of a 2.1 GHz Xeon, 2026-11-16):

    venv/bin/python -I trial.py > output.txt

What it does:

1. Branin (d = 2) and Borehole (d = 8) as in Surjanovic and Bingham's Virtual
   Library of Simulation Experiments (formulas re-typed from the published
   mathematics; their R code is GPL-2.0 and was not copied).
2. Training designs: Latin hypercubes from scipy.stats.qmc, n = 5d, 10d, 20d,
   ten design seeds each; 1,000 held-out points from a separate Latin hypercube.
3. Models: Gaussian process (scikit-learn, Matern 5/2 with one length scale per
   input), HistGradientBoostingRegressor with defaults, and with settings for
   small data.
4. Error on the held-out points (RMSE, max abs error, Q2, RMSE / range) against
   the cross-validation estimate from the training runs alone (5-fold, and
   leave-one-out for the GP), coverage of the GP's 95 % intervals.
5. A noisy Branin (Gaussian noise added) with a WhiteKernel, and a replicated
   design with per-point noise (stochastic-kriging style, alpha per point).
6. Extrapolation outside the training box.
7. Refit determinism, saved model sizes (pickle, skops, ONNX, JSON of data and
   hyperparameters), ONNX and JSON-refit agreement with the fitted model.

Seeds are fixed integers given to scipy and scikit-learn (research code; the
product would draw them from the spec 1 stream scheme).
"""

from __future__ import annotations

import json
import pickle
import time
import warnings
from typing import Any

import numpy as np
import scipy
import sklearn
from scipy.stats import qmc
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.model_selection import KFold, cross_val_predict

N_TEST = 1000
SEEDS = list(range(10))
TEST_SEED = 999_999
Z95 = 1.959963984540054


# ---------------------------------------------------------------- functions
def branin(x: np.ndarray) -> np.ndarray:
    """Branin, x1 in [-5, 10], x2 in [0, 15]; global minimum 0.397887."""
    a, b, c = 1.0, 5.1 / (4 * np.pi**2), 5 / np.pi
    r, s, t = 6.0, 10.0, 1 / (8 * np.pi)
    x1, x2 = x[:, 0], x[:, 1]
    return a * (x2 - b * x1**2 + c * x1 - r) ** 2 + s * (1 - t) * np.cos(x1) + s


BRANIN_BOX = np.array([[-5.0, 10.0], [0.0, 15.0]])


def borehole(x: np.ndarray) -> np.ndarray:
    """Borehole water flow (m3/yr); inputs rw, r, Tu, Hu, Tl, Hl, L, Kw."""
    rw, r, tu, hu, tl, hl, length, kw = (x[:, i] for i in range(8))
    lnr = np.log(r / rw)
    return (2 * np.pi * tu * (hu - hl)) / (
        lnr * (1 + 2 * length * tu / (lnr * rw**2 * kw) + tu / tl)
    )


BOREHOLE_BOX = np.array(
    [
        [0.05, 0.15],
        [100.0, 50000.0],
        [63070.0, 115600.0],
        [990.0, 1110.0],
        [63.1, 116.0],
        [700.0, 820.0],
        [1120.0, 1680.0],
        [9855.0, 12045.0],
    ]
)


def lhs(d: int, n: int, seed: int) -> np.ndarray:
    """Unit-cube Latin hypercube (scipy.stats.qmc), seeded."""
    return qmc.LatinHypercube(d=d, seed=seed).random(n)


def to_box(u: np.ndarray, box: np.ndarray) -> np.ndarray:
    return qmc.scale(u, box[:, 0], box[:, 1])


# ---------------------------------------------------------------- models
def make_gp(d: int, noise: bool = False, alpha: Any = 1e-10) -> GaussianProcessRegressor:
    kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
        length_scale=[0.5] * d, length_scale_bounds=(1e-2, 1e3), nu=2.5
    )
    if noise:
        kernel = kernel + WhiteKernel(1e-2, (1e-8, 1e1))
    return GaussianProcessRegressor(
        kernel=kernel,
        alpha=alpha,
        normalize_y=True,
        n_restarts_optimizer=5,
        random_state=0,
    )


def make_hgb_default() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(random_state=0)


def make_hgb_small() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        min_samples_leaf=2, max_iter=500, learning_rate=0.05, random_state=0
    )


MODELS = {"GP": make_gp, "HGB-default": make_hgb_default, "HGB-small": make_hgb_small}


def build(name: str, d: int) -> Any:
    return make_gp(d) if name == "GP" else MODELS[name]()


# ---------------------------------------------------------------- metrics
def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    err = p - y
    rmse = float(np.sqrt(np.mean(err**2)))
    q2 = float(1 - np.sum(err**2) / np.sum((y - y.mean()) ** 2))
    return {
        "rmse": rmse,
        "maxabs": float(np.max(np.abs(err))),
        "q2": q2,
        "nrmse": rmse / float(np.ptp(y)),
    }


def loo_gp_fixed(
    gp: GaussianProcessRegressor, x: np.ndarray, y: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Leave-one-out with the hyperparameters fitted on all runs (Jones et al. 1998)."""
    n = len(y)
    mu, sd = np.empty(n), np.empty(n)
    for i in range(n):
        keep = np.arange(n) != i
        g = GaussianProcessRegressor(
            kernel=gp.kernel_, alpha=gp.alpha, optimizer=None, normalize_y=True
        )
        g.fit(x[keep], y[keep])
        m, s = g.predict(x[i : i + 1], return_std=True)
        mu[i], sd[i] = m[0], s[0]
    return mu, sd


def cv5(name: str, d: int, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    kf = KFold(n_splits=5, shuffle=True, random_state=0)
    return cross_val_predict(build(name, d), x, y, cv=kf)


def fmt(v: float) -> str:
    return f"{v:.4g}"


def summary(vals: list[float]) -> str:
    a = np.array(vals)
    return f"median {fmt(np.median(a))} [min {fmt(a.min())}, max {fmt(a.max())}]"


# ---------------------------------------------------------------- study 1
def study_clean(fname: str, f: Any, box: np.ndarray, ns: list[int]) -> None:
    d = box.shape[0]
    ut = lhs(d, N_TEST, TEST_SEED)
    yt = f(to_box(ut, box))
    print(f"\n=== {fname} (d={d}); test y range {fmt(yt.min())} to {fmt(yt.max())}")
    for n in ns:
        for name in MODELS:
            rows: dict[str, list[float]] = {
                k: []
                for k in (
                    "rmse",
                    "maxabs",
                    "q2",
                    "nrmse",
                    "cv5_rmse",
                    "cv5_q2",
                    "ratio5",
                    "loo_rmse",
                    "loo_q2",
                    "ratio_loo",
                    "cov95",
                    "loo_cov95",
                    "loo_out3",
                    "fit_s",
                )
            }
            nwarn = 0
            for seed in SEEDS:
                u = lhs(d, n, seed)
                y = f(to_box(u, box))
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    m = build(name, d)
                    t0 = time.perf_counter()
                    m.fit(u, y)
                    rows["fit_s"].append(time.perf_counter() - t0)
                    if name == "GP":
                        p, s = m.predict(ut, return_std=True)
                        rows["cov95"].append(float(np.mean(np.abs(p - yt) <= Z95 * s)))
                    else:
                        p = m.predict(ut)
                    met = metrics(yt, p)
                    for k in ("rmse", "maxabs", "q2", "nrmse"):
                        rows[k].append(met[k])
                    pc = cv5(name, d, u, y)
                    mc = metrics(y, pc)
                    rows["cv5_rmse"].append(mc["rmse"])
                    rows["cv5_q2"].append(mc["q2"])
                    rows["ratio5"].append(mc["rmse"] / met["rmse"])
                    if name == "GP":
                        mu, sd = loo_gp_fixed(m, u, y)
                        ml = metrics(y, mu)
                        rows["loo_rmse"].append(ml["rmse"])
                        rows["loo_q2"].append(ml["q2"])
                        rows["ratio_loo"].append(ml["rmse"] / met["rmse"])
                        z = (y - mu) / sd
                        rows["loo_cov95"].append(float(np.mean(np.abs(z) <= Z95)))
                        rows["loo_out3"].append(float(np.sum(np.abs(z) > 3)))
                    nwarn += len(w)
            print(f"-- n={n} ({n // d}d) {name}  [10 design seeds; warnings raised: {nwarn}]")
            for k, v in rows.items():
                if v:
                    print(f"   {k:10s} {summary(v)}")


# ---------------------------------------------------------------- study 2
def study_noisy() -> None:
    print("\n=== Noisy Branin: y + N(0, sd^2), GP with WhiteKernel")
    d, box = 2, BRANIN_BOX
    ut = lhs(d, N_TEST, TEST_SEED)
    ft = branin(to_box(ut, box))
    for sd_noise in (5.0, 20.0):
        for n in (20, 40, 80):
            r: dict[str, list[float]] = {
                k: []
                for k in (
                    "rmse_vs_f",
                    "q2_vs_f",
                    "q2_vs_obs",
                    "cv5_rmse_obs",
                    "test_rmse_obs",
                    "noise_sd_fit",
                    "cov95_f_latent",
                    "cov95_obs_full",
                )
            }
            for seed in SEEDS:
                u = lhs(d, n, seed)
                rng = np.random.default_rng(10_000 + seed)
                y = branin(to_box(u, box)) + rng.normal(0, sd_noise, n)
                yt_obs = ft + np.random.default_rng(20_000 + seed).normal(0, sd_noise, N_TEST)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    gp = make_gp(d, noise=True).fit(u, y)
                    p, s = gp.predict(ut, return_std=True)
                    kf = KFold(n_splits=5, shuffle=True, random_state=0)
                    pc = cross_val_predict(make_gp(d, noise=True), u, y, cv=kf)
                noise_var = gp.kernel_.k2.noise_level * gp._y_train_std**2
                lat = np.sqrt(np.maximum(s**2 - noise_var, 0))
                mf = metrics(ft, p)
                r["rmse_vs_f"].append(mf["rmse"])
                r["q2_vs_f"].append(mf["q2"])
                r["q2_vs_obs"].append(metrics(yt_obs, p)["q2"])
                r["cv5_rmse_obs"].append(metrics(y, pc)["rmse"])
                r["test_rmse_obs"].append(metrics(yt_obs, p)["rmse"])
                r["noise_sd_fit"].append(float(np.sqrt(noise_var)))
                r["cov95_f_latent"].append(float(np.mean(np.abs(p - ft) <= Z95 * lat)))
                r["cov95_obs_full"].append(float(np.mean(np.abs(p - yt_obs) <= Z95 * s)))
            print(f"-- noise sd={sd_noise} n={n}")
            for k, v in r.items():
                print(f"   {k:15s} {summary(v)}")


def study_replicated() -> None:
    print("\n=== Replicated noisy Branin (stochastic-kriging style): 20 points x 5 replications,")
    print("    noise sd = 2 + 0.1*f(x) (heteroscedastic); GP on point means with alpha_i = s_i^2/5")
    d, box = 2, BRANIN_BOX
    ut = lhs(d, N_TEST, TEST_SEED)
    ft = branin(to_box(ut, box))
    out: dict[str, list[float]] = {
        "per_point_alpha_rmse": [],
        "per_point_alpha_q2": [],
        "per_point_alpha_cov95_f": [],
        "white_kernel_rmse": [],
        "white_kernel_q2": [],
        "white_kernel_cov95_f": [],
    }
    for seed in SEEDS:
        u = lhs(d, 20, seed)
        fx = branin(to_box(u, box))
        rng = np.random.default_rng(30_000 + seed)
        reps = fx[:, None] + rng.normal(0, 1, (20, 5)) * (2 + 0.1 * fx)[:, None]
        ybar, s2 = reps.mean(axis=1), reps.var(axis=1, ddof=1)
        # scikit-learn adds alpha after normalising y, so alpha is given in normalised units
        alpha = (s2 / 5) / np.var(ybar)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gp = make_gp(d, alpha=alpha).fit(u, ybar)
            p, s = gp.predict(ut, return_std=True)
            gw = make_gp(d, noise=True).fit(u, ybar)
            pw, sw = gw.predict(ut, return_std=True)
        nv = gw.kernel_.k2.noise_level * gw._y_train_std**2
        latw = np.sqrt(np.maximum(sw**2 - nv, 0))
        m1, m2 = metrics(ft, p), metrics(ft, pw)
        out["per_point_alpha_rmse"].append(m1["rmse"])
        out["per_point_alpha_q2"].append(m1["q2"])
        out["per_point_alpha_cov95_f"].append(float(np.mean(np.abs(p - ft) <= Z95 * s)))
        out["white_kernel_rmse"].append(m2["rmse"])
        out["white_kernel_q2"].append(m2["q2"])
        out["white_kernel_cov95_f"].append(float(np.mean(np.abs(pw - ft) <= Z95 * latw)))
    for k, v in out.items():
        print(f"   {k:24s} {summary(v)}")


# ---------------------------------------------------------------- study 3
def study_extrapolation() -> None:
    print(
        "\n=== Extrapolation: Branin GP trained on x1 in [-5, 2.5] (n=20), "
        "tested inside and outside"
    )
    d = 2
    inner = np.array([[-5.0, 2.5], [0.0, 15.0]])
    outer = np.array([[2.5, 10.0], [0.0, 15.0]])
    xi = to_box(lhs(d, N_TEST, TEST_SEED), inner)
    xo = to_box(lhs(d, N_TEST, TEST_SEED), outer)
    lo, hi = BRANIN_BOX[:, 0], BRANIN_BOX[:, 1]
    res: dict[str, list[float]] = {
        k: [] for k in ("q2_in", "q2_out", "rmse_in", "rmse_out", "cov95_in", "cov95_out")
    }
    for seed in SEEDS:
        x = to_box(lhs(d, 20, seed), inner)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gp = make_gp(d).fit((x - lo) / (hi - lo), branin(x))
        for tag, xt in (("in", xi), ("out", xo)):
            p, s = gp.predict((xt - lo) / (hi - lo), return_std=True)
            yt = branin(xt)
            m = metrics(yt, p)
            res[f"q2_{tag}"].append(m["q2"])
            res[f"rmse_{tag}"].append(m["rmse"])
            res[f"cov95_{tag}"].append(float(np.mean(np.abs(p - yt) <= Z95 * s)))
    for k, v in res.items():
        print(f"   {k:10s} {summary(v)}")


# ---------------------------------------------------------------- study 4
def study_smt() -> None:
    from smt.surrogate_models import KRG

    print("\n=== Cross-check with SMT KRG (squared exponential, defaults, seed 0), n = 10d")
    for fname, f, box in (("Branin", branin, BRANIN_BOX), ("Borehole", borehole, BOREHOLE_BOX)):
        d = box.shape[0]
        ut = lhs(d, N_TEST, TEST_SEED)
        yt = f(to_box(ut, box))
        q2s = []
        for seed in SEEDS:
            u = lhs(d, 10 * d, seed)
            sm = KRG(print_global=False, seed=0)
            sm.set_training_values(u, f(to_box(u, box)))
            sm.train()
            q2s.append(metrics(yt, sm.predict_values(ut).ravel())["q2"])
        print(f"   {fname} q2 {summary(q2s)}")


# ---------------------------------------------------------------- study 5
def study_portability() -> None:
    import onnxruntime as ort
    import skops.io as sio
    from skl2onnx import to_onnx

    print("\n=== Determinism, saved size and portability (Borehole, n=80, seed 0)")
    d, box = 8, BOREHOLE_BOX
    u = lhs(d, 80, 0)
    y = borehole(to_box(u, box))
    ut = lhs(d, N_TEST, TEST_SEED)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gp1, gp2 = make_gp(d).fit(u, y), make_gp(d).fit(u, y)
        h1, h2 = make_hgb_small().fit(u, y), make_hgb_small().fit(u, y)
    p1, s1 = gp1.predict(ut, return_std=True)
    p2, _ = gp2.predict(ut, return_std=True)
    print(f"   GP refit, same seed: predictions bit-identical: {np.array_equal(p1, p2)}")
    print(f"   GP fitted kernel: {gp1.kernel_}")
    print(
        f"   HGB refit, same seed: bit-identical: {np.array_equal(h1.predict(ut), h2.predict(ut))}"
    )
    # permuted training order
    perm = np.random.default_rng(1).permutation(80)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gp3 = make_gp(d).fit(u[perm], y[perm])
    p3 = gp3.predict(ut)
    print(
        f"   GP refit on permuted run order: max |diff| / range = "
        f"{fmt(float(np.max(np.abs(p3 - p1)) / np.ptp(y)))}"
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gp_raw = make_gp(d).set_params(normalize_y=False).fit(u, (y - y.mean()) / y.std())
    for name, m in (("GP", gp1), ("GP-normalize_y=False", gp_raw), ("HGB-small", h1)):
        pk = pickle.dumps(m, protocol=5)
        sk = sio.dumps(m)
        untrusted = sio.get_untrusted_types(data=sk)
        print(
            f"   {name}: pickle {len(pk)} bytes; skops {len(sk)} bytes; "
            f"skops untrusted types: {untrusted}"
        )
        with_std = name == "GP"
        onx = None
        for opts in ([{id(m): {"return_std": True}}] if with_std else []) + [None]:
            try:
                onx = to_onnx(m, u.astype(np.float64), target_opset=18, options=opts)
                with_std = opts is not None
                break
            except Exception as exc:  # record the converter's failure and go on
                kind = "with return_std" if opts else "mean only"
                print(
                    f"   {name}: ONNX conversion {kind} failed: {type(exc).__name__}: "
                    f"{str(exc)[:100]}"
                )
        if onx is None:
            continue
        ob = onx.SerializeToString()
        sess = ort.InferenceSession(ob, providers=["CPUExecutionProvider"])
        outs = sess.run(None, {sess.get_inputs()[0].name: ut.astype(np.float64)})
        yr = float(np.ptp(m.predict(u)))  # range of the model's own training target
        if name.startswith("GP"):
            ref, refs = m.predict(ut, return_std=True)
        else:
            ref = m.predict(ut)
        diff = float(np.max(np.abs(outs[0].ravel() - ref)) / yr)
        extra = ""
        if with_std:
            std_diff = float(np.max(np.abs(outs[1].ravel() - refs)) / yr)
            extra = f"; std max |diff| / range {fmt(std_diff)}"
        print(f"   {name}: ONNX {len(ob)} bytes; ONNX mean max |diff| / range {fmt(diff)}{extra}")

    # JSON of training data and fitted hyperparameters, refit without optimisation
    doc = {
        "x": u.tolist(),
        "y": y.tolist(),
        "kernel_theta_log": gp1.kernel_.theta.tolist(),
        "alpha": 1e-10,
        "normalize_y": True,
    }
    text = json.dumps(doc)
    back = json.loads(text)
    k = gp1.kernel.clone_with_theta(np.array(back["kernel_theta_log"]))
    g = GaussianProcessRegressor(
        kernel=k, alpha=back["alpha"], optimizer=None, normalize_y=back["normalize_y"]
    )
    g.fit(np.array(back["x"]), np.array(back["y"]))
    pj, sj = g.predict(ut, return_std=True)
    print(
        f"   GP as JSON (runs + hyperparameters): {len(text.encode())} bytes; refit without "
        f"optimiser: mean bit-identical {np.array_equal(pj, p1)}, max |diff| / range "
        f"{fmt(float(np.max(np.abs(pj - p1)) / np.ptp(y)))}, std max |diff| "
        f"{fmt(float(np.max(np.abs(sj - s1))))}"
    )
    t0 = time.perf_counter()
    for _ in range(100):
        g.predict(ut[:1])
    print(
        f"   GP single-point prediction: {fmt((time.perf_counter() - t0) / 100 * 1e3)} ms "
        f"(this machine)"
    )


def main() -> None:
    print(f"numpy {np.__version__}, scipy {scipy.__version__}, scikit-learn {sklearn.__version__}")
    study_clean("Branin", branin, BRANIN_BOX, [10, 20, 40])
    study_clean("Borehole", borehole, BOREHOLE_BOX, [40, 80, 160])
    study_noisy()
    study_replicated()
    study_extrapolation()
    study_smt()
    study_portability()


if __name__ == "__main__":
    main()
