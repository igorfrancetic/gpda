#!/usr/bin/env python3
"""
Difference-in-differences analysis of the GP Direct Access policy using the
NHS England Diagnostic Imaging Dataset trust panel (DID2014m4-2024m3.dta).

Why this exists
---------------
The original analysis compared GP direct access activity before and after the
November 2022 announcement with no control group, so it could not separate the
policy from the post-pandemic recovery in diagnostic services. The DID panel
splits each trust's cancer-detection imaging into GP direct referrals and all
other referrals, which supplies a within-trust control series.

Design
------
  treated series : GP direct referral events, policy-covered modalities
                   (CT chest/abdomen, brain MRI, ultrasound kidney/bladder,
                    ultrasound abdomen/pelvis)
  control series : non-GP referrals to the same trust, same modality, same month
                   (= total - GP)
  second control : chest x-ray, which the policy does not cover

  ln(events) ~ post x GP + trust-source fixed effects + month fixed effects
  standard errors clustered on trust

Data notes
----------
  * The file is named 2014m4-2024m3 but only contains April 2022 - March 2024.
  * February and March 2024 are structural zeros (every trust reports 0) and
    December 2023 - January 2024 decay sharply, so the analysis window is
    April 2022 to November 2023: 7 pre-announcement and 13 post months.
  * Restricted to NHS trusts (organisation codes beginning R), as in the
    original paper.

Usage
    python review/did_analysis.py [--dta DID2014m4-2024m3.dta]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

COVERED_GP = ["gpcdict", "gpcdimri", "gpcdiultra1", "gpcdiultra2"]
COVERED_TOT = ["totalcdict", "totalcdimri", "totalcdiultra1", "totalcdiultra2"]
WINDOW = ("2022-04-01", "2023-11-01")
ANNOUNCEMENT = "2022-11-01"
REFERENCE_MONTH = "2022-10-01"


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


def report(b, V, key, label):
    e, se = b[key], V.loc[key, key] ** 0.5
    p = 2 * (1 - stats.norm.cdf(abs(e / se)))
    print(f"  {label:<48s} {pct(e):+7.2f}%  "
          f"[{pct(e - 1.96 * se):+7.2f}, {pct(e + 1.96 * se):+7.2f}]  p={p:.4f}")


def load(dta):
    d = pd.read_stata(dta, convert_categoricals=False)
    d["ym"] = pd.to_datetime(d.yearmonth)
    d = d[(d.ym >= WINDOW[0]) & (d.ym <= WINDOW[1])]
    d = d[d.orgcode.str.startswith("R")]
    d["gp_cov"] = d[COVERED_GP].sum(axis=1, min_count=1)
    d["tot_cov"] = d[COVERED_TOT].sum(axis=1, min_count=1)
    return d


def two_series(d, gpcol, totcol):
    """Stack GP and non-GP (= total - GP) as two series per trust-month."""
    t = d[["orgcode", "ym", gpcol, totcol]].copy()
    t["ngp"] = t[totcol] - t[gpcol]
    a = t[["orgcode", "ym", gpcol]].rename(columns={gpcol: "y"}).assign(src="GP")
    b = t[["orgcode", "ym", "ngp"]].rename(columns={"ngp": "y"}).assign(src="nonGP")
    L = pd.concat([a, b]).dropna(subset=["y"])
    L = L[L.y > 0].copy()
    L["ly"] = np.log(L.y)
    L["post"] = (L.ym >= ANNOUNCEMENT).astype(float)
    L["gp"] = (L.src == "GP").astype(float)
    L["cell"] = L.orgcode + "_" + L.src
    L["mo"] = L.ym.astype(str)
    return L


def month_dummies(L, add):
    for mth in sorted(L.mo.unique())[1:]:
        add(f"mo_{mth}", (L.mo == mth).astype(float))


def fit_did(L, event=False):
    names, X = [], []

    def add(n, v):
        names.append(n)
        X.append(np.asarray(v, float))

    if event:
        for mth in sorted(L.mo.unique()):
            if mth != REFERENCE_MONTH:
                add(f"k_{mth}", (L.mo == mth).astype(float) * L["gp"])
    else:
        add("post#GP", L["post"] * L["gp"])
    month_dummies(L, add)
    return areg(L, "ly", names, np.column_stack(X), "cell", "orgcode")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dta", default="DID2014m4-2024m3.dta", type=Path)
    args = ap.parse_args()
    d = load(args.dta)

    print("=" * 82)
    print("SAMPLE")
    print("=" * 82)
    print(f"  trusts {d.orgcode.nunique()}   months {d.ym.nunique()}   "
          f"{d.ym.min().date()} to {d.ym.max().date()}  "
          f"(7 pre-announcement, 13 post)")
    print(f"  GP share of covered-modality cancer-detection events: "
          f"{d.gp_cov.sum() / d.tot_cov.sum():.1%}")
    print(f"  GP share of chest x-ray events: "
          f"{d.gpcdixray.sum() / d.totalcdixray.sum():.1%}")

    print("\n" + "=" * 82)
    print("1. MAIN DiD — GP direct referrals vs all other referrals, covered modalities")
    print("=" * 82)
    L = two_series(d, "gp_cov", "tot_cov")
    b, V, N, C = fit_did(L)
    print(f"  N={N:,} trust-source-months, {C} trusts")
    report(b, V, "post#GP", "GP vs non-GP after the announcement")

    print("\n" + "=" * 82)
    print(f"2. EVENT STUDY (reference month {REFERENCE_MONTH[:7]})")
    print("=" * 82)
    b, V, N, C = fit_did(L, event=True)
    for k in [i for i in b.index if i.startswith("k_")]:
        e, se = b[k], V.loc[k, k] ** 0.5
        flag = " *" if abs(e / se) > 1.96 else ""
        mark = "   <- announcement" if k[2:] == ANNOUNCEMENT else ""
        print(f"  {k[2:9]}  {pct(e):+7.2f}%  "
              f"[{pct(e - 1.96 * se):+7.2f}, {pct(e + 1.96 * se):+7.2f}]{flag}{mark}")
    pre = [i for i in b.index if i.startswith("k_2022-0")]
    print(f"\n  All {len(pre)} pre-announcement coefficients include zero: "
          f"{all(abs(b[k] / V.loc[k, k] ** 0.5) < 1.96 for k in pre)}")

    print("\n" + "=" * 82)
    print("3. CHEST X-RAY — a modality the policy does NOT cover")
    print("=" * 82)
    Lx = two_series(d, "gpcdixray", "totalcdixray")
    bx, Vx, Nx, Cx = fit_did(Lx)
    report(bx, Vx, "post#GP", "GP vs non-GP, chest x-ray")
    print("\n  If the policy alone were driving the covered-modality result, this")
    print("  placebo should be flat. It is not — see the discussion in REVIEW.md.")

    print("\n" + "=" * 82)
    print("4. WAITING TIMES — median days from request to test (the policy's stated aim)")
    print("=" * 82)
    pairs = {
        "CT (chest/abdomen)": ("mrtgpcdict", "mrttotalcdict"),
        "MRI (brain)": ("mrtgpcdimri", "mrttotalcdimri"),
        "Ultrasound (kidney/bladder)": ("mrtgpcdiultra1", "mrttotalcdiultra1"),
        "Ultrasound (abdomen/pelvis)": ("mrtgpcdiultra2", "mrttotalcdiultra2"),
        "Chest x-ray (not covered)": ("mrtgpcdixray", "mrttotalcdixray"),
    }
    for label, (gcol, tcol) in pairs.items():
        t = d[["orgcode", "ym", gcol, tcol]].dropna()
        a = t[["orgcode", "ym", gcol]].rename(columns={gcol: "y"}).assign(src="GP")
        bb = t[["orgcode", "ym", tcol]].rename(columns={tcol: "y"}).assign(src="All")
        L2 = pd.concat([a, bb])
        L2 = L2[L2.y > 0].copy()
        L2["ly"] = np.log(L2.y)
        L2["post"] = (L2.ym >= ANNOUNCEMENT).astype(float)
        L2["gp"] = (L2.src == "GP").astype(float)
        L2["cell"] = L2.orgcode + "_" + L2.src
        L2["mo"] = L2.ym.astype(str)
        b2, V2, _, _ = fit_did(L2)
        pre_m = t.loc[t.ym < ANNOUNCEMENT, gcol].median()
        post_m = t.loc[t.ym >= ANNOUNCEMENT, gcol].median()
        print(f"\n  {label}")
        print(f"    GP median wait {pre_m:.0f} -> {post_m:.0f} days")
        report(b2, V2, "post#GP", "    change vs all referrals at the same trust")
    print("\n  NOTE: the comparator is *all* referrals, which includes GP, so these")
    print("  differences are attenuated. Non-GP medians are not published separately.")


if __name__ == "__main__":
    main()
