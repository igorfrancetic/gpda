# Review of "Has NHS England's announcement on direct access investigations led to increased use of radiology tests?"

Reviewed version: 24/10/2024 (`24102024_GPlevel.docx`), with `appendix.pdf` and `replication.zip`.

Every number quoted below was produced by an independent re-implementation of `analysis.do` in
Python (`review/verify.py`), run against the same raw files in `replication.zip`. That
re-implementation reproduces the published results almost exactly, so the replication package works:

| Published (Stata) | Independent replication (Python) |
|---|---|
| Overall 2.709 [1.636, 3.781], N = 356,563 | 2.713 [1.640, 3.785], N = 356,563 |
| Tertile 1: 2.179 [0.736, 3.623] | 2.181 [0.738, 3.625] |
| Tertile 2: 0.0575 [−2.662, 2.776] | 0.049 [−2.669, 2.768] |
| Tertile 3: 9.522 [7.624, 11.42] | 9.527 [7.629, 11.425] |
| Map: NE&Y 24.82, NW 12.33, SW 11.71, SE 6.43, EoE 5.80, London 1.06, Midlands −0.95 | 24.83, 12.30, 11.73, 6.35, 5.82, 1.11, −0.93 |
| Trust means: MRI 4.34 (3.05), CT 4.98 (2.94), US 25.2 (21.40), ratio 1.48 (1.19) [0.195, 9.24] | identical to 3 s.f. |

Residual differences are entirely due to the random draw used to fill masked small counts.

---

## 1. Substantive issues

### 1.1 The stated study period does not match the estimation sample — **must fix**

The paper and the appendix both say the data cover **November 2021 to January 2024**, giving
"12 months prior to the policy being announced through to 14 months after".

The estimation sample is actually **October 2021 to February 2024**: `analysis.do` keeps
`yearmonth >= ym(2021,10)` and the event-study runs `dtime1`–`dtime29`, i.e. 29 months. That is
**13 months before** the announcement and **16 months after** it (November 2022 through February
2024). Figure 1 confirms this — its x-axis runs from −13 to +15 months.

Neither of the two stated figures (12 and 14) is right, and the start and end months are both off
by one. Referees check this.

### 1.2 The final month of data is incomplete — **should fix**

February 2024 is materially under-reported relative to every other month in the series:

| Month | GP–trust observations | Distinct practices |
|---|---|---|
| typical month | ~12,500 | ~6,500 |
| 2023-12 | 11,284 | 6,330 |
| 2024-01 | 10,973 | 5,985 |
| **2024-02** | **7,698** | **5,094** |

Because the surviving pairs are the higher-volume ones, the mean per observation is *highest* in
February 2024 (57.2) even though total volume collapses. This is also visible in Figure 1: the
last three points drop toward zero with much wider intervals.

Good news — it barely moves the headline:

| Sample | Estimate | 95% CI |
|---|---|---|
| As published (Oct 2021 – Feb 2024) | 2.71 | 1.64 to 3.78 |
| Excluding Feb 2024 | 2.79 | 1.72 to 3.85 |
| Excluding Jan + Feb 2024 | 2.82 | 1.77 to 3.87 |

**Recommendation:** drop February 2024, state the window as October 2021 – January 2024 (13 months
before, 15 after), and say in one sentence why. The estimate gets slightly *larger*, so nothing is
lost.

### 1.3 No control group, and the pre-period is not flat — **the biggest gap**

This is the issue most likely to attract a referee's attention, and the paper currently does not
mention it at all.

The design is a pre/post comparison with practice and ICB fixed effects and month-of-year dummies.
There is no unexposed group, so identification rests entirely on the assumption that nothing else
would have changed activity at November 2022 — during a period when NHS diagnostic services were
still recovering from the pandemic.

Adding a single linear time trend to the published specification:

| Specification | Post-announcement level shift | 95% CI | Fitted trend |
|---|---|---|---|
| Level shift only (as published) | **2.71** | 1.64 to 3.78 | — |
| + linear time trend | **0.30** | −0.94 to 1.54 | +0.162/month |
| + trend and post-policy slope change | 0.39 | −0.86 to 1.64 | +0.137/month, slope change +0.036 |

A common upward trend of about 0.16 referrals per practice–trust pair per month absorbs the entire
effect.

Two things push back the other way, and both are worth reporting:

- **Placebo tests inside the pre-period find nothing.** Assigning a fictitious announcement to
  March, May or July 2022 and estimating on the pre-policy window alone gives −0.54, −0.04 and
  +0.03 — no spurious discontinuities.
- The month-by-month estimates show a visible step at the announcement rather than smooth growth.

So the honest reading is: there *is* a discontinuity at the announcement, but the data cannot
distinguish a step change from a continuation of an existing upward trajectory. The revised
manuscript states this in a new "Strengths and limitations" section, and softens the causal
language ("has coincided with" rather than "appears to have had some effect in increasing").

**Recommendation:** the strongest fix is a comparison series. NHS England's Diagnostic Imaging
Dataset publishes imaging activity by source of referral. Consultant-requested activity, or
modalities outside the policy's scope, would give a control group and turn this into a
difference-in-differences rather than an uncontrolled before-and-after. That is a much stronger
paper and uses data you can already get.

### 1.4 Figure 1 is generated from a specification that is hard to interpret — **should fix**

Models `m1` and `m2` include `b12.time#c.k_mri`, `b12.time#c.k_ct`, `b12.time#c.k_us` (and
`b12.time#c.totalfte` in `m2`). Two consequences:

1. **The interaction base is the wrong month.** The event-study dummies omit `dtime13` (October
   2022, the intended reference), but the interactions use `b12.time` — September 2022. The two
   reference periods should be the same month.
2. **The plotted coefficients are conditional on zero scanners and zero staff.** With the
   interactions in the model, each `dtime` coefficient is the month effect evaluated at
   `k_mri = k_ct = k_us = totalfte = 0` — a trust that does not exist. That is not the average
   month-by-month change the caption describes.

This is not cosmetic. Estimating the same event study *without* the time-varying interactions
changes the picture: every pre-announcement coefficient becomes negative and significant relative
to October 2022 (mean −1.85), i.e. activity was climbing steadily through the pre-period, whereas
the published figure shows a pre-period scattered around zero. The average post-announcement effect
is unchanged (+1.62 vs +1.63), so only the pre-trend picture differs — which is exactly the thing
§1.3 turns on.

**Recommendation:** plot the event study from the simple specification (no time×trust
interactions), keep October 2022 as the single reference month, and show the interacted version as
a robustness check if you want it. `review/robustness.do` has the code.

### 1.5 The staff-to-scanner gradient is described as monotonic, but it is not

The paper says increases "were greater amongst GPs working in areas served by trusts which had
higher staff-to-assets ratio". The pattern is +2.18 (tertile 1), +0.06 (tertile 2), +9.52
(tertile 3) — a large effect concentrated in the top tertile, not a gradient. The middle tertile is
flat, and the *bottom* tertile is significantly positive.

Also, the top-tertile result is the most striking number in the paper — **+19.5%, nearly four times
the national figure** — and it currently appears only as "0.195" in an unlabelled table column. The
revised text quantifies it.

### 1.6 Regional claims: naming and characterisation

- "North East" should be **"North East and Yorkshire"** — that is the NHS England region name, and
  it is the one used in the code and on the map.
- "Sout West" → "South West" (typo).
- The paper says London, South East, East of England and the Midlands "has not changed markedly".
  East of England is +5.8% and South East +6.4% — point estimates comparable to the national
  average, just imprecisely estimated. "Not statistically distinguishable from zero" is accurate;
  "not changed markedly" is not.
- The regional numbers currently exist **only inside the Figure 2 image**. They should be in a
  table so they are readable, quotable and machine-searchable. The revised manuscript adds Table 2.

---

## 2. Table, figure and presentation fixes

### 2.1 Table 1 is broken

In the submitted `.docx` the header row is mangled — the column labels and the "Difference compared
to pre-policy / 95% Confidence Interval" sub-header sit in the wrong cells, so the table does not
parse as laid out.

More importantly, the last column is labelled **"% change compared to pre-policy mean"** but
contains **fractions**: 0.0524, 0.0414, 0.00106, 0.195. A reader takes these at face value as
0.05%, 0.04%, 0.001% and 0.2% — off by two orders of magnitude, and the text elsewhere correctly
says "5.2 percent". Multiply by 100 and add a `%` sign. The revised Table 1 does this.

### 2.2 The significance note is attached to the wrong object and is incomplete

The note "Stars indicate differences that are statistically significant at 99 (**) and 99.9 (***)
percent confidence level" sits under **Figure 2**, but describes the stars in **Table 1**. It also
omits `*` (95%), which `esttab` will print. Standard form: `* p < 0.05, ** p < 0.01, *** p < 0.001`.

### 2.3 Figure 2 (map) needs a legend and a significance convention

The exported map has no visible colour scale, and it colours all seven regions on a continuous
ramp even though four are not statistically distinguishable from zero — which visually implies
gradations the data do not support. Consider hatching or greying the non-significant regions, and
make sure `legend(pos(11))` actually renders in the exported PNG.

### 2.4 The abstract contains no numbers

For a short analysis piece the abstract is the part most people read. It currently restates the
conclusion without a single estimate. The revised abstract carries the headline effect, the
tertile-3 result, the three significant regions and the design caveat.

---

## 3. Wording and factual corrections

| Location | Issue | Fix |
|---|---|---|
| Affiliation 2 | "Uoniversity of Applied Sciences" | "University" |
| Trends, ¶1 | "the receiving NHS trusts **were had** on average" | "had on average" |
| Trends, ¶1 | "referred on average 52 direct access patients per month to each receiving NHS trust, or about 97 patients per month overall" | Correct (51.7 per practice–trust pair; 96.7 per practice across all its trusts) but ambiguous — the two numbers are different denominators. Reworded. |
| Regional ¶ | "Sout West" | "South West" |
| Box 1 | "number of MRI, CT and Ultrasound **scans** available" | **scanners** — these are asset counts, not activity |
| Box 1, last sentence | "High numbers can also signal a small asset count compared to Trust staffing, but the adjusted differences reported in this piece ensure this is not the case." | Does not follow — controlling for asset counts does not "ensure" the ratio is not driven by fleet size. Rewritten to state what the controls actually do. |
| Background | "The policy came without any additional workforce or infrastructure resources" | Stated as fact with no citation. Softened to "was not accompanied by dedicated additional workforce or equipment funding". |
| Conclusion / abstract | "assiduity of regional health organisations" | "how actively regional health organisations have implemented the policy" |
| Figure 1 ¶ | "shows the difference each month (prior and) after" | stray parenthetical removed |
| Appendix | "our coefficients **or** interest" | "of interest" |
| Appendix | "count of MRI, CT, and Ultrasound **scans** owned"; "per **scan**" | "scanners" |
| Appendix | "namely clinical radiology, medical oncology" | "namely clinical radiology and medical oncology" |

---

## 4. Things that are fine — do not change them

Worth recording, because two of these look like bugs and are not:

- **`rename providername orgcode` is correct.** The header row of `gpda.csv` is mislabelled at
  source: the column headed `Provider Code` holds the trust *name* and the column headed
  `Provider Name` holds the *code*. The do-file's apparently backwards rename compensates for this.
  Add a one-line comment so no future reader "fixes" it.
- **The region label mapping is correct.** `label define reglab` assumes `egen dregion =
  group(Region)` orders the regions alphabetically, and the seven NHS England region strings do
  sort exactly as labelled. Fragile but currently right.
- **The imputation of masked small counts is robust and is the conservative choice.** Masked cells
  are 37.6% of the analysis sample but only **1.4% of total referral volume**. The headline
  estimate is essentially invariant to how they are filled:

  | Treatment of masked cells | Estimate |
  |---|---|
  | Random U{1,2,3}, seed 333 (published) | 2.725 |
  | All set to 1 / 2 / 3 | 2.713 / 2.715 / 2.717 |
  | Random draw, seeds 1 / 42 / 999 | 2.718 / 2.714 / 2.714 |
  | **Dropped entirely** | **8.240** |

  Dropping them would have inflated the estimate three-fold by selecting on high-volume
  practice–trust pairs. This is a genuinely good methodological decision and deserves a sentence in
  the paper rather than being buried in the appendix — it pre-empts an obvious referee question.
  The masked share also rises slightly after the announcement (36.6% → 38.5%), which argues against
  a mechanical "fewer masked cells because volumes rose" artefact.

---

## 5. Suggested additional analyses

In rough order of value:

1. **Add a comparison series** (see §1.3) — the single change that would most improve the paper.
2. **Report the trend-adjusted estimate and the placebo tests** in the paper, not just in a
   response to reviewers. Being first to name the weakness is much stronger than being asked about
   it.
3. **Cluster or absorb at the practice–trust pair level**, not just the practice. Observations are
   practice–trust–months; `nrtrusts` is computed in `analysis.do` but never used. Practices refer
   to 1.87 trusts on average, so a shift in *which* trust a practice uses is currently not separated
   from a change in its total volume.
4. **Extend the series.** The published data stop in early 2024 and the policy has now had over
   three years to bed in. Whether the North/South gap persisted, closed or widened is a more
   interesting question than the first-year response, and the answer is in data you already have
   access to.
5. Consider a count model (Poisson/negative binomial with practice fixed effects) as a robustness
   check — the outcome is a count with a long right tail, currently handled by trimming above the
   99th percentile.

---

## 6. Files in this review

| File | Contents |
|---|---|
| `review/paper_revised.docx` | Full revised manuscript incorporating everything above |
| `review/verify.py` | Independent replication + all robustness checks quoted here (Python, needs only pandas/numpy/openpyxl and the unzipped `replication/` folder) |
| `review/robustness.do` | Stata code for the additional analyses, to append to `analysis.do` |
| `review/results/` | Saved output of `verify.py` |

**Before submitting, re-run the trend-adjusted and placebo estimates in Stata** using
`review/robustness.do` and confirm they match the numbers in §1.3. They are quoted in the revised
manuscript's limitations section, and they should be your own Stata output rather than a
third-party reimplementation, even though the two agree everywhere they have been compared.
