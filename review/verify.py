#!/usr/bin/env python3
"""
Independent replication of analysis.do, plus the robustness checks quoted in
review/REVIEW.md.

The point of this file is that the published results can be checked without
Stata, and that the robustness numbers in the review are reproducible rather
than asserted.

Usage
-----
    unzip replication.zip            # gives ./replication/
    pip install pandas numpy openpyxl
    python review/verify.py [--data replication/datain] > review/results/verify_output.txt

Everything below mirrors analysis.do, capital.do and workforce.do. Where this
file departs from the do-files it says so in a comment.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 333  # same seed as analysis.do


# --------------------------------------------------------------------------
# Estimation: Stata's areg with cluster-robust standard errors
# --------------------------------------------------------------------------
def areg(df, y, names, X, absorb, cluster):
    """Absorb one high-dimensional fixed effect, cluster-robust SEs.

    Reproduces `areg y X, absorb(absorb) cluster(cluster)`, including Stata's
    small-sample correction G/(G-1) * (N-1)/(N-K) with K counting the absorbed
    intercepts.
    """
    g = pd.factorize(df[absorb])[0]
    G = g.max() + 1
    counts = np.bincount(g, minlength=G).astype(float)

    def demean(A):
        A = np.asarray(A, float)
        if A.ndim == 1:
            A = A[:, None]
        means = np.vstack([
            np.bincount(g, weights=A[:, j], minlength=G) / counts
            for j in range(A.shape[1])
        ]).T
        return A - means[g]

    yd = demean(df[y].to_numpy(float)).ravel()
    Xd = demean(X)

    keep = ~np.all(np.abs(Xd) < 1e-10, axis=0)          # drop absorbed columns
    Xd, names = Xd[:, keep], [n for n, k in zip(names, keep) if k]

    XtXi = np.linalg.pinv(Xd.T @ Xd)
    b = XtXi @ (Xd.T @ yd)
    e = yd - Xd @ b

    N, K = len(yd), Xd.shape[1] + G
    cl = pd.factorize(df[cluster])[0]
    C = cl.max() + 1
    sums = np.zeros((C, Xd.shape[1]))
    np.add.at(sums, cl, Xd * e[:, None])
    adj = (C / (C - 1)) * ((N - 1) / (N - K))
    V = adj * (XtXi @ (sums.T @ sums) @ XtXi)
    se = np.sqrt(np.diag(V))

    res = pd.DataFrame(
        {"coef": b, "se": se, "lo": b - 1.96 * se, "hi": b + 1.96 * se},
        index=names,
    )
    return res, N, C


def stars(coef, se):
    t = abs(coef / se)
    return "***" if t > 3.291 else "**" if t > 2.576 else "*" if t > 1.960 else ""


# --------------------------------------------------------------------------
# Data build (capital.do + workforce.do + the cleaning block of analysis.do)
# --------------------------------------------------------------------------
def ym(year, month):
    """Stata's ym(): months since January 1960."""
    return (year - 1960) * 12 + (month - 1)


def build_panel(datain: Path):
    # --- capital.do: imaging asset counts as at 31 March 2023
    cap = pd.read_excel(
        datain / "National-Imaging-Data-Collection-Asset-Count-2022-23-v1.xlsx",
        sheet_name="ICB, Imaging Network and Trust",
        header=13, usecols="B:S",                       # == cellrange(B14:S151) firstrow
    ).rename(columns={"Organisation Code": "orgcode", "MRI": "k_mri",
                      "CT": "k_ct", "Ultrasound": "k_us"})
    cap = cap[cap.orgcode.notna()]
    cap["k_tot"] = cap.k_mri + cap.k_ct + cap.k_us

    # --- workforce.do: clinical radiology + medical oncology FTE, October 2022
    wf = pd.read_csv(datain / "NHS Workforce Statistics, October 2022 medical staff.csv")
    wf = wf[wf.Specialty.isin(["Clinical radiology", "Medical oncology"])]
    wf = (wf.groupby("Org code", as_index=False)["Total FTE"].sum()
            .rename(columns={"Org code": "orgcode", "Total FTE": "totalfte"}))

    cap = cap.merge(wf, on="orgcode", how="left")
    cap["staffassetratio"] = cap.totalfte / cap.k_tot
    ok = cap.staffassetratio.notna()
    cap.loc[ok, "tert_ratio"] = pd.qcut(cap.loc[ok, "staffassetratio"], 3,
                                        labels=[1, 2, 3]).astype(int)

    # --- GP direct access counts.
    # NOTE: the header of gpda.csv is mislabelled at source. The column headed
    # "Provider Code" holds the trust NAME and "Provider Name" holds the CODE.
    # analysis.do's `rename providername orgcode` compensates for this; the
    # column names below reflect what the columns actually contain.
    g = pd.read_csv(
        datain / "gpda.csv", sep=";", encoding="utf-8-sig", dtype=str, header=0,
        names=["fy", "monthm", "providername", "orgcode", "gpcode", "gpname", "rc"],
    )
    g["rc"] = pd.to_numeric(g.rc, errors="coerce")
    g["masked"] = g.rc.isna()                           # NHS England masks counts of 1-3

    rng = np.random.default_rng(SEED)
    g["gpda"] = g.rc.copy()
    g.loc[g.masked, "gpda"] = rng.integers(1, 4, int(g.masked.sum()))

    # financial-year month (M01 = April) -> calendar year and month
    g["month"] = g.monthm.str[1:].astype(int).map(
        {1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11, 9: 12, 10: 1, 11: 2, 12: 3})
    fy = g.fy.astype(int)
    g["year"] = np.where(g.month > 3, fy // 100, fy % 100 + 2000)
    g["yearmonth"] = (g.year - 1960) * 12 + (g.month - 1)

    g = g[g.providername.notna() & (g.providername != "NULL")
          & g.orgcode.notna() & (g.orgcode != "NULL")
          & g.gpcode.notna() & (g.gpcode != "NULL")]
    g = g[g.orgcode.str.startswith("R")]                 # NHS trusts only

    m = g.merge(
        cap[["orgcode", "Region", "ICB - Integrated Care Board", "k_mri", "k_ct",
             "k_us", "totalfte", "staffassetratio", "tert_ratio"]],
        on="orgcode", how="inner")
    m = m[m.totalfte.notna()]                           # keep if _merge==3

    m = m[m.gpda <= m.gpda.quantile(0.99)]              # trim >99th percentile
    m = m[m.yearmonth >= ym(2021, 10)]                  # analysis.do keeps from Oct 2021
    m["post"] = (m.yearmonth >= ym(2022, 11)).astype(int)
    m["icb"] = m["ICB - Integrated Care Board"]
    m["t"] = m.yearmonth - ym(2022, 11)                 # 0 = announcement month
    return m, cap


# --------------------------------------------------------------------------
# Design matrices
# --------------------------------------------------------------------------
def design(d, postvar="post", trend=None, ycol="gpda"):
    """Model o2 of analysis.do, optionally with a linear trend."""
    names, X = [], []

    def add(n, v):
        names.append(n)
        X.append(np.asarray(v, float))

    add("post", d[postvar])
    if trend in ("linear", "linear_break"):
        add("t", d.t)
    if trend == "linear_break":
        add("post#t", d[postvar] * d.t)
    for k in ("k_mri", "k_ct", "k_us"):
        add(k, d[k])
        add(f"post#{k}", d[postvar] * d[k])
    add("totalfte", d.totalfte)
    add("post#totalfte", d[postvar] * d.totalfte)
    for mo in range(1, 13):                             # b10.month
        if mo != 10:
            add(f"month_{mo}", (d.month == mo).astype(float))
    for c in sorted(d.icb.unique())[1:]:                # i.icbid
        add(f"icb_{c}", (d.icb == c).astype(float))
    return names, np.column_stack(X)


def fit(d, label, postvar="post", trend=None, ycol="gpda", width=40):
    names, X = design(d, postvar, trend, ycol)
    res, N, _ = areg(d, ycol, names, X, "gpcode", "gpcode")
    r = res.loc["post"]
    pre = d.loc[d[postvar] == 0, ycol].mean()
    extra = ""
    if "t" in res.index:
        extra += f"  trend={res.loc['t', 'coef']:+.3f}/mo"
    if "post#t" in res.index:
        extra += f"  slope_change={res.loc['post#t', 'coef']:+.3f}"
    print(f"{label:<{width}s} b={r.coef:7.3f}{stars(r.coef, r.se):<3s} "
          f"[{r.lo:7.3f},{r.hi:7.3f}]  N={N:7d}  pre={pre:6.2f}  "
          f"%chg={100 * r.coef / pre:6.2f}{extra}")
    return res, N, pre


def event_study(d, interact_base=None, label=""):
    """Month-by-month estimates, October 2022 omitted as the reference month.

    interact_base=None  -> no time-varying trust controls (recommended, §1.4)
    interact_base=12    -> analysis.do's b12.time# interactions, as published
    """
    tvals = sorted(d.yearmonth.unique())
    idx = {t: i + 1 for i, t in enumerate(tvals)}
    time = d.yearmonth.map(idx)
    ref = idx[ym(2022, 10)]

    names, X = [], []

    def add(n, v):
        names.append(n)
        X.append(np.asarray(v, float))

    for t in idx.values():
        if t != ref:
            add(f"k={t - ref - 1}", (time == t).astype(float))
    cols = ["k_mri", "k_ct", "k_us", "totalfte"]
    for c in cols:
        add(c, d[c])
    if interact_base is not None:
        for c in cols:
            for t in idx.values():
                if t != interact_base:
                    add(f"{c}#t{t}", (time == t).astype(float) * d[c])
    for mo in range(1, 13):
        if mo != 10:
            add(f"month_{mo}", (d.month == mo).astype(float))
    for c in sorted(d.icb.unique())[1:]:
        add(f"icb_{c}", (d.icb == c).astype(float))

    res, N, _ = areg(d, "gpda", names, np.column_stack(X), "gpcode", "gpcode")
    es = res[res.index.str.startswith("k=")].copy()
    es["k"] = [int(i.split("=")[1]) for i in es.index]
    print(f"\n--- {label} (N={N:,}) ---")
    for _, r in es.iterrows():
        print(f"  k={int(r.k):+3d}: {r.coef:7.2f} [{r.lo:7.2f},{r.hi:7.2f}]{stars(r.coef, r.se)}")
    print(f"  mean pre-announcement coefficient : {es[es.k < 0].coef.mean():+.2f}")
    print(f"  mean post-announcement coefficient: {es[es.k >= 0].coef.mean():+.2f}")
    return es


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="replication/datain", type=Path)
    ap.add_argument("--skip-event-study", action="store_true",
                    help="the interacted event study fits ~200 regressors and is slow")
    args = ap.parse_args()

    if not args.data.exists():
        sys.exit(f"data directory not found: {args.data} (unzip replication.zip first)")

    m, cap = build_panel(args.data)

    print("=" * 78)
    print("1. REPLICATION OF PUBLISHED RESULTS")
    print("=" * 78)

    print("\nTrust-level descriptives (paper: 4.34/3.05, 4.98/2.94, 25.2/21.40, 1.48/1.19)")
    d = cap[cap.totalfte.notna()]
    print(d[["totalfte", "k_mri", "k_ct", "k_us", "staffassetratio"]]
          .agg(["count", "mean", "std", "min", "max"]).T.round(3).to_string())

    pre = m[m.post == 0]
    per_practice = m.groupby(["gpcode", "yearmonth"]).agg(
        tot=("gpda", "sum"), post=("post", "first"))
    print(f"\npre-announcement mean per practice-trust-month : {pre.gpda.mean():.2f}  (paper: 51.70)")
    print(f"pre-announcement mean per practice-month, all trusts: "
          f"{per_practice[per_practice.post == 0].tot.mean():.2f}  (paper: ~97)")
    print(f"practices: {m.gpcode.nunique():,}   trusts: {m.orgcode.nunique()}   "
          f"months: {m.yearmonth.nunique()}   observations: {len(m):,}")

    print("\nTable 1 (paper: 2.709 / 2.179 / 0.0575 / 9.522)")
    fit(m, "Overall")
    for tert in (1, 2, 3):
        fit(m[m.tert_ratio == tert], f"Staff-to-scanner tertile {tert}")

    print("\nFigure 2, by NHS England region "
          "(map: 24.82 / 12.33 / 11.71 / 6.43 / 5.80 / 1.06 / -0.95)")
    for r in sorted(m.Region.unique()):
        fit(m[m.Region == r], r)

    print("\n" + "=" * 78)
    print("2. MONTHLY COVERAGE  (REVIEW.md section 1.2)")
    print("=" * 78)
    cov = m.groupby("yearmonth").agg(obs=("gpda", "size"), practices=("gpcode", "nunique"),
                                     mean=("gpda", "mean"))
    cov.index = [f"{1960 + i // 12}-{i % 12 + 1:02d}" for i in cov.index]
    print(cov.round(2).to_string())
    print("\nFebruary 2024 is materially incomplete: it is the last month supplied and "
          "\ncarries ~60% of a normal month's observations.")

    print("\nSensitivity to the incomplete tail:")
    fit(m, "As published (Oct 2021 - Feb 2024)")
    fit(m[m.yearmonth <= ym(2024, 1)], "Excluding Feb 2024")
    fit(m[m.yearmonth <= ym(2023, 12)], "Excluding Jan + Feb 2024")

    print("\n" + "=" * 78)
    print("3. PRE-EXISTING TREND AND PLACEBO TESTS  (REVIEW.md section 1.3)")
    print("=" * 78)
    fit(m, "Level shift only (as published)")
    fit(m, "+ linear time trend", trend="linear")
    fit(m, "+ trend and post-policy slope change", trend="linear_break")

    print("\nPlacebo announcements inside the pre-policy window (Oct 2021 - Oct 2022):")
    prewin = m[m.yearmonth <= ym(2022, 10)].copy()
    for y, mo in ((2022, 3), (2022, 5), (2022, 7)):
        prewin["placebo"] = (prewin.yearmonth >= ym(y, mo)).astype(int)
        fit(prewin, f"Placebo announcement {y}-{mo:02d}", postvar="placebo")

    print("\n" + "=" * 78)
    print("4. MASKED SMALL COUNTS  (REVIEW.md section 4)")
    print("=" * 78)
    print(f"masked share of cells      : {100 * m.masked.mean():.1f}%"
          f"   (pre {100 * m.loc[m.post == 0, 'masked'].mean():.1f}%,"
          f" post {100 * m.loc[m.post == 1, 'masked'].mean():.1f}%)")
    print(f"masked share of volume     : {100 * m.loc[m.masked, 'gpda'].sum() / m.gpda.sum():.2f}%")
    print()
    fit(m, f"Random U{{1,2,3}}, seed {SEED} (published)")
    for v in (1, 2, 3):
        m["alt"] = np.where(m.masked, v, m.rc)
        fit(m, f"All masked cells set to {v}", ycol="alt")
    for s in (1, 42, 999):
        rng = np.random.default_rng(s)
        m["alt"] = m.rc.copy()
        m.loc[m.masked, "alt"] = rng.integers(1, 4, int(m.masked.sum()))
        fit(m, f"Random U{{1,2,3}}, seed {s}", ycol="alt")
    fit(m[~m.masked], "Masked cells dropped (NOT recommended)")

    if not args.skip_event_study:
        print("\n" + "=" * 78)
        print("5. EVENT STUDY SPECIFICATIONS  (REVIEW.md section 1.4)")
        print("=" * 78)
        event_study(m, None, "No time-varying trust controls (recommended)")
        event_study(m, 12, "As published: b12.time# interactions (Figure 1)")

    print("\nDone.")


if __name__ == "__main__":
    main()
