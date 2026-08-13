# BJR Short Communication

**More tests, not faster tests: GP direct access to cancer diagnostic imaging in England, 2018–2025**

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

Differences-in-differences against non-GP referrals to the same trust, in the
same test group and month, April 2018 – March 2025 excluding the pandemic year,
clustered on 160 trusts. 29 post-announcement months.

| | Activity | Median wait |
|---|---|---|
| **All covered test groups** | **+10.1%** (5.1 to 15.3) | +3.1% (−1.8 to 8.3) |
| Brain MRI | +35.2% (24.7 to 46.7) | +3.9% (−4.2 to 12.7) |
| CT chest and abdomen/pelvis | +14.9% (6.6 to 23.8) | −6.4% (−13.1 to 0.9) |
| Chest radiography | +12.9% (8.5 to 17.6) | −8.7% (−29.2 to 17.7) |
| Ultrasound abdomen/pelvis | +7.1% (−0.2 to 15.0) | −2.3% (−9.8 to 5.7) |
| Ultrasound kidney/bladder *(not named in guidance)* | +8.2% (−4.6 to 22.8) | −10.2% (−19.8 to 0.4) |

No waiting-time change reaches significance in any group. Robustness: placebo
announcement −1.1% (p=0.69); with a differential linear trend +16.8%;
truncated at November 2023 +10.7%; adjusting for regional community diagnostic
centre exposure +13.5%, with the exposure term itself null.

Reproduce with `python review/did_analysis.py`; full output in
`review/results/did_analysis_output.txt`.

## Before submitting

1. **Confirm BJR's current limits** for Short Communications — main text,
   references, figures and tables. The abstract limit (200 words) and the
   "Advances in knowledge" requirement are already met; OUP's site was not
   reachable to verify the rest.
2. **Run the Stata pipeline.** `stata/did_pipeline.do` is self-contained: it
   imports the raw published spreadsheets from `datain/`, builds the panel,
   estimates every model in the paper, runs the community diagnostic centre
   check and the Callaway–Sant'Anna robustness, and writes the tables and
   figures. Nothing else is needed — no derived `.dta` files, no Python.

   It has **not been executed** (no Stata in the environment it was written
   in), so treat it as unverified until you run it. Every section carries its
   expected estimate as a comment, so a divergence will be obvious. Header rows
   in the source workbooks move between years, so columns are located by
   content rather than position.

   **Two-way fixed effects is primary**; Callaway–Sant'Anna is a robustness
   check. Treatment timing is common, not staggered — every treated series is
   treated in November 2022 and the comparators are never treated — so the
   negative-weighting problem that motivates CS does not arise, and TWFE
   additionally admits GP-specific calendar-month controls, which matters
   because seasonality is the dominant nuisance in these data.

3. **Complete the STROBE checklist** and attach it as supplementary material —
   the Methods section already states that it was followed.
4. **Decide the relationship to the earlier practice-level paper.** This
   analysis supersedes it: it uses a control series, a pre-pandemic baseline and
   the correct modality set. See `../review/REVIEW.md` for what changed and why.
