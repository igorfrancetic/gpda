# GP direct access to cancer diagnostic imaging in England

Data and code for the paper **"More tests, not faster tests: GP direct access
to cancer diagnostic imaging in England, 2018–2025"**.

In November 2022 NHS England gave general practitioners direct access to a
defined minimum set of imaging tests — chest radiography, CT of the chest and
of the abdomen/pelvis, ultrasound of the abdomen/pelvis, and brain MRI — for
patients with symptoms below the threshold for an urgent suspected cancer
referral. This repository asks whether that changed the volume and the
timeliness of GP-requested cancer-detection imaging.

**Headline:** GP direct referrals for these tests rose about 10% relative to
all other referrals to the same trust, and stayed elevated for 29 months. No
test group showed a significant improvement in median waiting time from
request to test. More tests, not faster tests.

Correspondence: Igor Francetic, igor.francetic@manchester.ac.uk

## What is where

| Path | Contents |
|---|---|
| `manuscript/` | The manuscript, both figures (300 dpi PNG and vector PDF), and the scripts that generate them |
| `stata/did_pipeline.do` | **The complete analysis.** Runs end to end from the raw spreadsheets — no other input needed |
| `datain/raw_trust/` | NHS England Diagnostic Imaging Dataset published tables, financial years 2018-19 to 2024-25 |
| `datain/cdc/` | Community diagnostic centre opening dates, from the government's operational list |
| `datain/gpda.xlsx` | Quarterly GP Direct Access activity by practice and provider, 2018/19 to 2025/26 Q1 |
| `review/` | Python implementation of the same analysis, plus the review that produced it |

## Reproducing the paper

Everything in the paper comes from one command:

```stata
do stata/did_pipeline.do
```

It imports the published tables, builds the panel, estimates every model,
runs the community diagnostic centre check and the Callaway–Sant'Anna
robustness, and writes the tables and all three figures — Figure 1, Figure 2
and the event-study plot — into `stata/tables/` and `stata/figures/`. It needs `reghdfe`, `ftools`,
`estout`, `coefplot`, `csdid` and `drdid` from SSC.

A Python implementation of the same analysis is in `review/`, which is what
the manuscript's numbers were computed from:

```bash
python review/build_panel.py          # raw spreadsheets -> analysis panel
python review/did_analysis.py         # main models
python review/cdc_confounder_test.py  # community diagnostic centres
python review/practice_panel.py       # practice-level quarterly analysis
```

## The design in one paragraph

GP direct referrals are the treated series. Referrals from all other sources
to the **same trust, in the same test group and month** are the control, which
is what makes this a difference-in-differences rather than a before-and-after
comparison. Estimation is log-linear with trust-by-source and calendar-time
fixed effects, GP-specific calendar-month effects for seasonality, and
standard errors clustered by trust. April 2018 to March 2025, excluding the
pandemic disruption of March 2020 to March 2021: 160 trusts, 71 months, 29 of
them after the announcement.

Source setting is published as "All" and "GP Direct Access". For counts the
control is All minus GP. Medians cannot be differenced, so for waiting times
the comparator is the All median, which still contains GP activity and
therefore attenuates those estimates towards zero.

## Data provenance

Everything derives from two tables of the Diagnostic Imaging Dataset,
published per financial year by NHS England:

- **Table 4** — counts of imaging activity, using groups of tests suitable for
  diagnosing cancer, labelled by body site
- **Table 5** — the same groups, median days from request to test

Both are provider × test group × source setting × month. Note that header rows
move between years and tables, so both pipelines locate columns by content
rather than by position.

Ultrasound of the kidney or bladder is the one published test group the
guidance does not name, and is reported throughout as a comparator.

## Superseded material

An earlier version of this work analysed a bespoke practice-level extract
without a control series, and reported that trusts with fewer imaging staff
per scanner were less able to deliver the increase. That finding did not
survive: it fails under trust-level clustering, under a pooled interaction
model, and under a within-practice design using 527,597 practice–provider
observations, where the point estimates reverse sign. `review/REVIEW.md`
records what changed and why.

The original appendix (`appendix.pdf`) and replication package
(`replication.zip`) have been removed from the working tree. They remain in
git history at commit `77a13ea` and can be recovered with:

```bash
git show 77a13ea:appendix.pdf > appendix.pdf
git show 77a13ea:replication.zip > replication.zip
```

`review/verify.py`, `review/capacity_analysis.py`, `review/robustness.do` and
the capacity section of `review/practice_panel.py` document that superseded
analysis and require the replication package to run. Nothing in the current
paper depends on them.
