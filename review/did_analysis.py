#!/usr/bin/env python3
"""
Difference-in-differences analysis of the GP Direct Access policy using the
NHS England Diagnostic Imaging Dataset trust panel (data/*.dta).

Design
------
  treated series : GP direct referral events, policy-covered modalities
                   (CT chest/abdomen, brain MRI, ultrasound kidney/bladder,
                    ultrasound abdomen/pelvis)
  control series : non-GP referrals to the same trust, same modality, same
                   month (= total - GP)
  placebo        : chest x-ray, which the policy does not cover

  ln(events) ~ post x GP
             + trust-source fixed effects
             + calendar-time fixed effects
             + GP-specific calendar-month effects   (seasonality)
  standard errors clustered on trust

Why the baseline matters
------------------------
Diagnostic activity collapsed in 2020-21 and recovered through 2021-22, so a
pre-period that starts in 2021 uses a depressed counterfactual and flatters any
post-2022 comparison. Every estimate is therefore reported against two
baselines: April 2021 (post-COVID recovery) and April 2018 excluding the
pandemic year (pre-COVID norm).

Data notes
----------
  * data/ holds one file per financial year, 2018-19 to 2023-24.
  * February and March 2024 are structural zeros (every trust reports 0) and
    December 2023 - January 2024 decay sharply, so the series is cut at
    November 2023.
  * The pandemic disruption (March 2020 - March 2021) is dropped from the
    long-baseline models.
  * Restricted to NHS trusts (organisation codes beginning R), as in the
    original paper.

Usage
    python review/did_analysis.py [--data data]
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

COVERED_GP = ["gpcdict", "gpcdimri", "gpcdiultra1", "gpcdiultra2"]
COVERED_TOT = ["totalcdict", "totalcdimri", "totalcdiultra1", "totalcdiultra2"]
ANNOUNCEMENT = "2022-11-01"
SERIES_END = "2023-11-01"
COVID = ("2020-03-01", "2021-03-01")
REFERENCE_MONTH = "2022-10-01"

WAIT_PAIRS = {
    "CT (chest/abdomen)": ("mrtgpcdict", "mrttotalcdict"),
    "MRI (brain)": ("mrtgpcdimri", "mrttotalcdimri"),
    "Ultrasound (kidney/bladder)": ("mrtgpcdiultra1", "mrttotalcdiultra1"),
    "Ultrasound (abdomen/pelvis)": ("mrtgpcdiultra2", "mrttotalcdiultra2"),
    "Chest x-ray (NOT covered)": ("mrtgpcdixray", "mrttotalcdixray"),
}


def areg(df, y, names, X, absorb, cluster):
    """Absorb one fixed effect; cluster-robust SEs with Stata's correction."""
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
    cl = pd.factorize(df[cluster])[0]
    C = cl.max() + 1
    s = np.zeros((C, Xd.shape[1]))
    np.add.at(s, cl, Xd * e[:, None])
    V = (C / (C - 1)) * ((N - 1) / (N - K)) * (XtXi @ (s.T @ s) @ XtXi)
    return pd.Series(b, index=names), pd.DataFrame(V, index=names, columns=names), N, C


def pct(x):
    return 100 * (np.exp(x) - 1)


def line(b, V, key, label):
    e, se = b[key], V.loc[key, key] ** 0.5
    p = 2 * (1 - stats.norm.cdf(abs(e / se)))
    print(f"  {label:<54s} {pct(e):+6.2f}%  "
          f"[{pct(e - 1.96 * se):+6.2f}, {pct(e + 1.96 * se):+6.2f}]  p={p:.4f}")


def load(folder):
    files = sorted(glob.glob(str(Path(folder) / "*.dta")))
    if not files:
        raise SystemExit(f"no .dta files in {folder}")
    D = pd.concat([pd.read_stata(f, convert_categoricals=False) for f in files],
                  ignore_index=True)
    D["ym"] = pd.to_datetime(D.yearmonth)
    D = D[D.orgcode.str.startswith("R")]
    D = D[D.ym <= SERIES_END]
    D["gp_cov"] = D[COVERED_GP].sum(axis=1, min_count=1)
    D["tot_cov"] = D[COVERED_TOT].sum(axis=1, min_count=1)
    return D


def stack(d, gpcol, totcol, subtract=True):
    """Two series per trust-month: GP, and the comparator."""
    t = d[["orgcode", "ym", gpcol, totcol]].copy()
    if subtract:
        t["cmp"] = t[totcol] - t[gpcol]          # counts: non-GP is total minus GP
    else:
        t["cmp"] = t[totcol]                     # medians cannot be differenced
    a = t[["orgcode", "ym", gpcol]].rename(columns={gpcol: "y"}).assign(src="GP")
    b = t[["orgcode", "ym", "cmp"]].rename(columns={"cmp": "y"}).assign(src="CMP")
    L = pd.concat([a, b]).dropna(subset=["y"])
    L = L[L.y > 0].copy()
    L["ly"] = np.log(L.y)
    L["post"] = (L.ym >= ANNOUNCEMENT).astype(float)
    L["gp"] = (L.src == "GP").astype(float)
    L["cell"] = L.orgcode + "_" + L.src
    L["mo"] = L.ym.astype(str)
    L["cm"] = L.ym.dt.month
    return L


def fit(L, event=False, gp_season=True):
    names, X = [], []

    def add(n, v):
        names.append(n)
        X.append(np.asarray(v, float))

    if event:
        for m in sorted(L.mo.unique()):
            if m != REFERENCE_MONTH:
                add(f"k_{m}", (L.mo == m).astype(float) * L["gp"])
    else:
        add("post#GP", L["post"] * L["gp"])
    if gp_season:
        for c in sorted(L.cm.unique())[1:]:
            add(f"gpM{c}", (L.cm == c).astype(float) * L["gp"])
    for m in sorted(L.mo.unique())[1:]:
        add(f"mo_{m}", (L.mo == m).astype(float))
    return areg(L, "ly", names, np.column_stack(X), "cell", "orgcode")


def baselines(D):
    """The two counterfactual windows, each as a filtered frame."""
    recovery = D[D.ym >= "2021-04-01"]
    precovid = D[~((D.ym >= COVID[0]) & (D.ym <= COVID[1]))]
    return [("April 2021 baseline (post-COVID recovery)", recovery),
            ("April 2018 baseline, pandemic year dropped", precovid)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    args = ap.parse_args()
    D = load(args.data)

    print("=" * 88)
    print("SAMPLE")
    print("=" * 88)
    print(f"  trusts {D.orgcode.nunique()}   months {D.ym.nunique()}   "
          f"{D.ym.min().date()} to {D.ym.max().date()}")
    print(f"  GP share of covered-modality cancer-detection events: "
          f"{D.gp_cov.sum() / D.tot_cov.sum():.1%}")
    for lab, dd in baselines(D):
        pre = dd[dd.ym < ANNOUNCEMENT]
        print(f"  {lab}: {pre.ym.nunique()} pre-announcement months")

    print("\n" + "=" * 88)
    print("1. MAIN DiD — GP direct referrals vs all other referrals, covered modalities")
    print("=" * 88)
    for lab, dd in baselines(D):
        L = stack(dd, "gp_cov", "tot_cov")
        b, V, N, C = fit(L, gp_season=False)
        line(b, V, "post#GP", f"{lab}  (N={N:,}, {C} trusts)")
        b, V, N, C = fit(L, gp_season=True)
        line(b, V, "post#GP", "   + GP-specific calendar-month effects")

    print("\n" + "=" * 88)
    print("2. CHEST X-RAY PLACEBO — a modality the policy does not cover")
    print("=" * 88)
    for lab, dd in baselines(D):
        L = stack(dd, "gpcdixray", "totalcdixray")
        b, V, N, C = fit(L)
        line(b, V, "post#GP", lab)
    print("\n  A policy-specific effect requires this to be flat. It is not.")

    print("\n" + "=" * 88)
    print(f"3. EVENT STUDY (reference month {REFERENCE_MONTH[:7]}, April 2021 baseline)")
    print("=" * 88)
    L = stack(D[D.ym >= "2021-04-01"], "gp_cov", "tot_cov")
    b, V, N, C = fit(L, event=True)
    ks = [i for i in b.index if i.startswith("k_")]
    pre = [k for k in ks if k[2:] < ANNOUNCEMENT]
    nsig = sum(abs(b[k] / V.loc[k, k] ** 0.5) > 1.96 for k in pre)
    print(f"  {len(pre)} pre-announcement months, {nsig} significant at 5% "
          f"(chance expectation {0.05 * len(pre):.1f})")
    for k in ks:
        e, se = b[k], V.loc[k, k] ** 0.5
        flag = "  *" if abs(e / se) > 1.96 else ""
        mark = "   <- announcement" if k[2:] == ANNOUNCEMENT else ""
        print(f"  {k[2:9]}  {pct(e):+7.2f}%  "
              f"[{pct(e - 1.96 * se):+7.2f}, {pct(e + 1.96 * se):+7.2f}]{flag}{mark}")

    print("\n" + "=" * 88)
    print("4. WAITING TIMES — median days request-to-test (the policy's stated aim)")
    print("=" * 88)
    for label, (gcol, tcol) in WAIT_PAIRS.items():
        print(f"\n  {label}")
        for lab, dd in baselines(D):
            t = dd[["orgcode", "ym", gcol, tcol]].dropna()
            L = stack(t, gcol, tcol, subtract=False)
            b, V, _, _ = fit(L)
            pre_m = t.loc[t.ym < ANNOUNCEMENT, gcol].median()
            post_m = t.loc[t.ym >= ANNOUNCEMENT, gcol].median()
            line(b, V, "post#GP",
                 f"    {lab[:38]:<38s} ({pre_m:.0f}->{post_m:.0f}d)")
    print("\n  NOTE: the comparator is *all* referrals, which includes GP, so these")
    print("  differences are attenuated. Non-GP medians are not published separately.")


if __name__ == "__main__":
    main()
