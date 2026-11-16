"""Trial 1: two-parameter Weibull MLE with right-censored data.

Known answer: NIST/SEMATECH e-Handbook of Statistical Methods, section 8.4.1.3
"A Weibull maximum likelihood estimation example" (read 2026-11-16):
failures at 54, 187, 216, 240, 244, 335, 361, 373, 375, 386 h, and 10 units
removed unfailed at 500 h. Published: eta = 606.5280, beta = 1.7208,
log-likelihood -75.135, AIC 154.27.

Install (scratch venv, Python 3.12, Linux):
    uv venv -p 3.12 venv
    VIRTUAL_ENV=venv uv pip install reliability==0.9.0 lifelines==0.30.3 \
        scipy==1.18.1 surpyval==0.28 predictr==0.1.37 numpy==2.5.5
Run:
    venv/bin/python weibull_censored.py > output-weibull_censored.txt
"""

import contextlib
import io
import warnings
from importlib.metadata import version

import numpy as np

FAILURES = [54, 187, 216, 240, 244, 335, 361, 373, 375, 386]
CENSORED = [500] * 10
ETA, BETA, LOGLIK = 606.5280, 1.7208, -75.135


def loglik(eta: float, beta: float) -> float:
    """Weibull log-likelihood with right censoring (closed form, for checking)."""
    x = np.array(FAILURES, float)
    c = np.array(CENSORED, float)
    log_f = np.log(beta / eta) + (beta - 1) * np.log(x / eta) - (x / eta) ** beta
    log_s = -((c / eta) ** beta)
    return float(log_f.sum() + log_s.sum())


def report(name: str, eta: float, beta: float) -> None:
    ll = loglik(eta, beta)
    print(
        f"{name:<34} eta={eta:.4f} beta={beta:.4f} loglik={ll:.3f} "
        f"| d_eta={eta - ETA:+.4f} d_beta={beta - BETA:+.5f} "
        f"| match 4 s.f.: {f'{eta:.4g}' == f'{ETA:.4g}' and f'{beta:.4g}' == f'{BETA:.4g}'}"
    )


def with_reliability() -> None:
    from reliability.Fitters import Fit_Weibull_2P

    with contextlib.redirect_stdout(io.StringIO()):
        fit = Fit_Weibull_2P(
            failures=FAILURES,
            right_censored=CENSORED,
            show_probability_plot=False,
            print_results=False,
        )
    report(f"reliability {version('reliability')}", fit.alpha, fit.beta)


def with_lifelines() -> None:
    from lifelines import WeibullFitter

    t = FAILURES + CENSORED
    e = [1] * len(FAILURES) + [0] * len(CENSORED)
    fit = WeibullFitter().fit(t, event_observed=e)
    report(f"lifelines {version('lifelines')} WeibullFitter", fit.lambda_, fit.rho_)


def with_scipy() -> None:
    from scipy import stats

    data = stats.CensoredData(uncensored=FAILURES, right=CENSORED)
    beta, _loc, eta = stats.weibull_min.fit(data, floc=0)
    report(f"scipy {version('scipy')} weibull_min.fit", eta, beta)


def with_surpyval() -> None:
    import surpyval

    x = FAILURES + CENSORED
    c = [0] * len(FAILURES) + [1] * len(CENSORED)
    fit = surpyval.Weibull.fit(x=x, c=c)
    eta, beta = fit.params
    report(f"surpyval {version('surpyval')} Weibull.fit", eta, beta)


def with_predictr() -> None:
    from predictr import Analysis

    a = Analysis(df=FAILURES, ds=CENSORED, show=False)
    with contextlib.redirect_stdout(io.StringIO()):
        a.mle()
    report(f"predictr {version('predictr')} Analysis.mle", a.eta, a.beta)


def main() -> None:
    warnings.simplefilter("ignore")
    print("NIST 8.4.1.3 published: eta=606.5280 beta=1.7208 loglik=-75.135")
    print(f"closed-form loglik at published values: {loglik(ETA, BETA):.3f}")
    for trial in (with_reliability, with_lifelines, with_scipy, with_surpyval, with_predictr):
        try:
            trial()
        except Exception as exc:  # research script: report and continue
            print(f"{trial.__name__}: FAILED {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
