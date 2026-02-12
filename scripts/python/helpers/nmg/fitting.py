"""Shared fitting functions for NMG scripts."""

from __future__ import annotations

import math

import numpy as np

try:
    from scipy.optimize import minimize

    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False


def fit_log_weighted(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    lx = np.log(x)
    ly = np.log(y)
    weight_sum = float(np.sum(w))
    mean_x = float(np.dot(w, lx) / weight_sum)
    mean_y = float(np.dot(w, ly) / weight_sum)
    var_x = float(np.dot(w, (lx - mean_x) ** 2) / weight_sum)
    if var_x <= 0:
        raise ValueError("Variance of log-income is non-positive.")
    cov_xy = float(np.dot(w, (lx - mean_x) * (ly - mean_y)) / weight_sum)
    exponent = cov_xy / var_x
    intercept = mean_y - exponent * mean_x
    scale = math.exp(intercept)
    return scale, exponent


def fit_nls_weighted(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    if not HAVE_SCIPY:
        raise ValueError("SciPy is required for nls_weighted.")

    init_scale, init_exponent = fit_log_weighted(x, y, w)

    def objective(params: np.ndarray) -> float:
        scale, exponent = params
        if scale <= 0:
            return float("inf")
        with np.errstate(over="ignore", invalid="ignore"):
            prediction = scale * np.power(x, exponent)
        if not np.isfinite(prediction).all():
            return float("inf")
        error = y - prediction
        return float(np.dot(w, error * error))

    result = minimize(
        objective,
        x0=np.array([init_scale, init_exponent], dtype=float),
        method="Nelder-Mead",
        options={"maxiter": 20000, "xatol": 1e-10, "fatol": 1e-10},
    )
    if not result.success and (not np.isfinite(result.fun)):
        raise ValueError("NLS optimization failed.")
    scale, exponent = result.x
    if scale <= 0 or not np.isfinite(scale) or not np.isfinite(exponent):
        raise ValueError("NLS optimization produced invalid parameters.")
    return float(scale), float(exponent)
