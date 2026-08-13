# BJR Short Communication

**More tests, not faster tests: GP direct access to cancer diagnostic imaging in England, 2018–2023**

| File | Contents |
|---|---|
| `BJR_manuscript.docx` | Manuscript. Structured abstract (194 words), Advances in knowledge, IMRAD, declarations, Table 1, both figures, 12 references. Main text ~1,260 words. |
| `BJR_Fig1.png` / `.pdf` | GP direct referrals as a share of all cancer-detection imaging, April 2018 – November 2023 |
| `BJR_Fig2.png` / `.pdf` | Adjusted change in activity and in median request-to-test wait, by modality |
| `bjrfigs.py` | Generates both figures from the CSVs below |
| `bjr_fig1.csv`, `bjr_fig2.csv` | Figure inputs, written by `../review/did_analysis.py` |

Figures are 300 dpi PNG plus vector PDF. Convert to TIFF at submission if the
journal requires it (`sips -s format tiff`, ImageMagick `convert`, or export the
PDF from any vector editor) — do not upscale the PNG.

## The headline numbers

All estimates are differences-in-differences against non-GP referrals to the
same trust, in the same modality and month, over April 2018 – November 2023
excluding the pandemic disruption, clustered on 154 trusts.

| | Activity | Median wait |
|---|---|---|
| All covered modalities | **+10.4%** (5.8 to 15.3) | +5.9% (−0.04 to 12.1) |
| Brain MRI | +29.0% (20.0 to 38.7) | +7.1% (−1.0 to 15.8) |
| CT chest and abdomen/pelvis | +14.8% (5.7 to 24.7) | −1.4% (−8.5 to 6.2) |
| Chest radiography | +13.4% (9.6 to 17.4) | −2.4% (−21.7 to 21.7) |
| Ultrasound abdomen/pelvis | +6.1% (−0.7 to 13.5) | +2.2% (−6.0 to 11.2) |
| Ultrasound kidney/bladder *(not named in guidance)* | +4.1% (−6.7 to 16.3) | −3.1% (−13.6 to 8.7) |

Reproduce with `python review/did_analysis.py`; full output in
`review/results/did_analysis_output.txt`.

## Before submitting

1. **Confirm BJR's current limits** for Short Communications — main text,
   references, figures and tables. The abstract limit (200 words) and the
   "Advances in knowledge" requirement are already met; OUP's site was not
   reachable to verify the rest.
2. **Re-run the models in Stata.** `stata/did_pipeline.do` is the full pipeline
   for this manuscript — panel build, main DiD under both baselines,
   by-modality, waiting times including the pooled estimate, placebo,
   differential trend, a Callaway–Sant'Anna event study, and table export. It
   is written linearly: one long panel, then every analysis as a single
   estimation command selected with an `if` condition.

   It has **not been executed** (no Stata in the environment it was written
   in), but its data-build steps were verified against the Python and produce
   an identical panel: 9,984 trust-months, 160 trusts, and stacked analysis
   samples of 8,214 and 14,617. Those totals are `assert`ed at the top, and
   every section carries its expected estimate as a comment.
   `review/robustness.do` covers the earlier practice-level analyses.

   **Two-way fixed effects is the primary estimator** (sections 03–06);
   Callaway–Sant'Anna (section 07) is a robustness check. Treatment timing here
   is common, not staggered — every treated series is treated in November 2022
   and the comparators are never treated — so the negative-weighting problem
   that motivates CS over TWFE does not arise, and TWFE additionally admits
   GP-specific calendar-month controls, which matters because seasonality is
   the dominant nuisance in these data. The two agree: CS gives about +9.1% on
   a seasonally adjusted outcome against +10.4% from TWFE. `csdid` carries no
   calendar-month controls, so section 07c repeats it on an outcome from which
   GP-specific seasonality has been removed using pre-announcement months only.

   The manuscript states this in one Methods sentence and reports the CS
   estimate in one Results sentence, citing Callaway and Sant'Anna (2021) as
   reference 11.
3. **Complete the STROBE checklist** and attach it as supplementary material —
   the Methods section already states that it was followed.
4. **Decide the relationship to the earlier practice-level paper.** This
   analysis supersedes it: it uses a control series, a pre-pandemic baseline and
   the correct modality set. See `../review/REVIEW.md` for what changed and why.
