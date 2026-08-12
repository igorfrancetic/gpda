#!/usr/bin/env python3
"""
Heterogeneity analysis for the GP direct access paper: does the change in
activity after the announcement differ by receiving-trust capacity or by region?

This script exists because the answer turned out to depend on two choices that
the published analysis makes implicitly:

  1. the level at which standard errors are clustered, and
  2. whether the post indicator is interacted with trust scanner counts and
     staffing.

Run after review/verify.py has built the panel (it reuses the same build).

    python review/capacity_analysis.py --data replication/datain
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

import sys
sys.path.insert(0, str(Path(__file__).parent))
from verify import build_panel, ym                      # noqa: E402


# --------------------------------------------------------------------------
def areg_multi(df, y, names, X, absorb, clusterings):
    """Absorb one FE; return coefficients with several clustering choices.

    clusterings: {label: column} or {label: [col_a, col_b]} for two-way
    (Cameron-Gelbach-Miller: V_a + V_b - V_ab).
    """
    g = pd.factorize(df[absorb])[0]
    G = g.max() + 1
    cnt = np.bincount(g, minlength=G).astype(float)

    def demean(A):
        A = np.asarray(A, float)
        if A.ndim == 1:
            A = A[:, None]
        mu = np.vstack([np.bincount(g, weights=A[:, j], minlength=G) / cnt
                        for j in range(A.shape[1])]).T
        return A - mu[g]

    yd = demean(df[y].to_numpy(float)).ravel()
    Xd = demean(X)
    keep = ~np.all(np.abs(Xd) < 1e-10, axis=0)
    Xd, names = Xd[:, keep], [n for n, k in zip(names, keep) if k]

    XtXi = np.linalg.pinv(Xd.T @ Xd)
    b = XtXi @ (Xd.T @ yd)
    e = yd - Xd @ b
    N, K = len(yd), Xd.shape[1] + G

    def meat(col):
        cl = pd.factorize(df[col])[0]
        C = cl.max() + 1
        s = np.zeros((C, Xd.shape[1]))
        np.add.at(s, cl, Xd * e[:, None])
        return s.T @ s, C

    out = {}
    for label, spec in clusterings.items():
        if isinstance(spec, list):
            m1, C1 = meat(spec[0])
            m2, C2 = meat(spec[1])
            df = df.assign(_both=df[spec[0]].astype(str) + "_" + df[spec[1]].astype(str))
            m12, _ = meat("_both")
            C = min(C1, C2)
            V = (C / (C - 1)) * ((N - 1) / (N - K)) * (XtXi @ (m1 + m2 - m12) @ XtXi)
        else:
            mm, C = meat(spec)
            V = (C / (C - 1)) * ((N - 1) / (N - K)) * (XtXi @ mm @ XtXi)
        out[label] = (pd.Series(b, index=names), pd.DataFrame(V, index=names, columns=names), C)
    return out, N


def contrast(b, V, weights):
    idx = list(b.index)
    v = np.zeros(len(idx))
    for k, w in weights.items():
        v[idx.index(k)] = w
    est = float(v @ b.to_numpy())
    se = float(np.sqrt(v @ V.to_numpy() @ v))
    return est, est - 1.96 * se, est + 1.96 * se, 2 * (1 - stats.norm.cdf(abs(est / se)))


def design(d, extra, post_x_trust):
    names, X = [], []

    def a(n, v):
        names.append(n)
        X.append(np.asarray(v, float))

    a("post", d.post)
    for n, v in extra:
        a(n, v)
    for k in ("k_mri", "k_ct", "k_us"):
        a(k, d[k])
        if post_x_trust:
            a(f"post#{k}", d.post * d[k])
    a("totalfte", d.totalfte)
    if post_x_trust:
        a("post#totalfte", d.post * d.totalfte)
    for mo in range(1, 13):
        if mo != 10:
            a(f"month_{mo}", (d.month == mo).astype(float))
    for c in sorted(d.icb.unique())[1:]:
        a(f"icb_{c}", (d.icb == c).astype(float))
    return names, np.column_stack(X)


def report(d, title, extra, contrasts, post_x_trust, second="orgcode"):
    names, X = design(d, extra, post_x_trust)
    res, N = areg_multi(d, "gpda", names, X, "gpcode",
                        {"practice": "gpcode", second: second})
    print(f"\n--- {title}   (N={N:,}) ---")
    print(f"{'contrast':<36s}{'est':>8s}   {'clustered on practice':>28s}   {'clustered on ' + second:>28s}")
    for label, w in contrasts:
        line, est = f"{label:<36s}", None
        for _, (b, V, C) in res.items():
            if not all(k in b.index for k in w):
                line += f"{'n/a':>28s}"
                continue
            e, lo, hi, p = contrast(b, V, w)
            if est is None:
                est = e
                line += f"{e:>8.2f}   "
            line += f"[{lo:7.2f},{hi:7.2f}] p={p:5.3f}   "
        print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="replication/datain", type=Path)
    args = ap.parse_args()

    m, _ = build_panel(args.data)
    m["icb"] = m["ICB - Integrated Care Board"]
    m["tert"] = m.tert_ratio.astype(int)
    m["bot"] = (m.tert == 1).astype(float)
    m["regid"] = m.Region
    m["t"] = m.yearmonth - ym(2022, 11)

    print("=" * 100)
    print("FINDING 1: the heterogeneity regressors vary at TRUST level, but the")
    print("published models cluster on PRACTICE.")
    print(f"  practices: {m.gpcode.nunique():,}    trusts: {m.orgcode.nunique()}    regions: {m.Region.nunique()}")
    print("=" * 100)

    tert = [("tert2", (m.tert == 2).astype(float)), ("tert3", (m.tert == 3).astype(float)),
            ("post#tert2", m.post * (m.tert == 2)), ("post#tert3", m.post * (m.tert == 3))]
    report(m, "Tertiles of staff-to-scanner ratio (published-style specification)", tert,
           [("Tertile 1 (fewest staff/scanner)", {"post": 1}),
            ("Tertile 2", {"post": 1, "post#tert2": 1}),
            ("Tertile 3 (most staff/scanner)", {"post": 1, "post#tert3": 1}),
            ("Tertile 3 - Tertile 1", {"post#tert3": 1}),
            ("Tertile 3 - Tertile 2", {"post#tert3": 1, "post#tert2": -1})],
           post_x_trust=True)

    binary = [("bot", m.bot), ("post#bot", m.post * m.bot)]
    report(m, "Bottom third vs upper two thirds, transparent specification", binary,
           [("Upper two thirds", {"post": 1}),
            ("Bottom third", {"post": 1, "post#bot": 1}),
            ("DIFFERENCE", {"post#bot": 1})],
           post_x_trust=False)

    regs = sorted(m.Region.unique())
    rextra = []
    for r in regs[1:]:
        rextra.append((f"R[{r}]", (m.Region == r).astype(float)))
        rextra.append((f"post#R[{r}]", m.post * (m.Region == r)))
    report(m, "Regions (reference = East of England)", rextra,
           [(f"{r} - East of England", {f"post#R[{r}]": 1}) for r in regs[1:]],
           post_x_trust=True, second="regid")

    print("\n" + "=" * 100)
    print("FINDING 2: the tertile pattern flips with the trust-control interactions.")
    print("=" * 100)
    for px, lab in ((False, "WITHOUT post x scanner counts / staffing"),
                    (True, "WITH post x scanner counts / staffing")):
        report(m, lab, tert,
               [("Tertile 1", {"post": 1}), ("Tertile 2", {"post": 1, "post#tert2": 1}),
                ("Tertile 3", {"post": 1, "post#tert3": 1})], post_x_trust=px)

    print("\n" + "=" * 100)
    print("FINDING 3: the capacity contrast does not survive group-specific trends.")
    print("=" * 100)
    trend = binary + [("t", m.t), ("t#bot", m.t * m.bot)]
    report(m, "Bottom third vs rest, with common and group-specific linear trends", trend,
           [("DIFFERENCE at the announcement", {"post#bot": 1}),
            ("differential trend per month", {"t#bot": 1})], post_x_trust=False)

    pre = m[m.yearmonth <= ym(2022, 10)].copy()
    pre["post"] = (pre.yearmonth >= ym(2022, 5)).astype(int)
    report(pre, "Placebo: fictitious announcement May 2022, pre-period only",
           [("bot", pre.bot), ("post#bot", pre.post * pre.bot)],
           [("DIFFERENCE", {"post#bot": 1})], post_x_trust=False)


if __name__ == "__main__":
    main()
