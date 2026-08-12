// ---------------------------------------------------------------------------
// Additional analyses recommended in review/REVIEW.md
//
// Append this to analysis.do, or run it after analysis.do has built the
// estimation sample (it assumes gpda, post, time, month, icbid, id, dregion,
// tert_ratio, k_mri, k_ct, k_us, totalfte and yearmonth are all in memory).
// ---------------------------------------------------------------------------

global assets_o k_mri k_ct k_us post#c.k_mri post#c.k_ct post#c.k_us
global assets_m k_mri k_ct k_us b13.time#c.k_mri b13.time#c.k_ct b13.time#c.k_us


// ---------------------------------------------------------------------------
// 1. Drop the incomplete final month (Feb 2024)                    REVIEW §1.2
// ---------------------------------------------------------------------------
// Feb 2024 has ~7,700 GP-trust observations vs ~12,500 in a typical month, and
// 5,094 practices vs ~6,500. Check the profile before deciding:

tab yearmonth if e(sample)
bysort yearmonth: egen npract = nvals(gpcode)
tabstat npract, by(yearmonth)

// Re-run the headline model on the complete months only.
qui: sum gpda if post==0 & yearmonth<=ym(2024,1)
scalar premean_c = r(mean)
eststo o2_complete: areg gpda post $assets_o c.totalfte post#c.totalfte ///
    b10.month i.icbid if yearmonth<=ym(2024,1), a(id) cluster(id)
estadd scalar mean    = `=premean_c'
estadd scalar perceff = r(table)[1,1]/`=premean_c'*100

// Expected: 2.79 [1.72, 3.85] -- slightly larger than the published 2.71.


// ---------------------------------------------------------------------------
// 2. Event study with a single, consistent reference month         REVIEW §1.4
// ---------------------------------------------------------------------------
// analysis.do omits dtime13 (Oct 2022) from the event-study dummies but bases
// the trust-characteristic interactions on b12.time (Sep 2022). Two problems:
// the reference months differ, and with the interactions in the model each
// dtime coefficient is evaluated at k_mri = k_ct = k_us = totalfte = 0.
//
// (a) Preferred figure: no time-varying trust interactions, one reference month.

eststo es_clean: areg gpda dtime1-dtime12 dtime14-dtime29 ///
    k_mri k_ct k_us c.totalfte b10.month i.icbid, a(id) cluster(id)
coefplot es_clean, vertical keep(dtime*) xlabel(, angle(45)) ///
    xtitle("Months relative to announcement") ytitle("# of monthly GP DAs") ///
    yline(0, lcol(red)) xline(13, lcol(green)) ///
    note("Note: Reference month is Oct 2022. No time-varying trust controls.")
graph export figures/eventstudy_clean.tif, replace

// (b) Interacted version, with the interaction base fixed to match (b13, not b12).

eststo es_interacted: areg gpda dtime1-dtime12 dtime14-dtime29 $assets_m ///
    c.totalfte b13.time#c.totalfte b10.month i.icbid, a(id) cluster(id)
coefplot es_interacted, vertical keep(dtime*) xlabel(, angle(45)) ///
    xtitle("Months relative to announcement") ytitle("# of monthly GP DAs") ///
    yline(0, lcol(red)) xline(13, lcol(green))
graph export figures/eventstudy_interacted.tif, replace

// In (a) every pre-announcement coefficient is negative and significant
// relative to Oct 2022 -- activity was already climbing before the policy.
// That pre-trend is what motivates section 3 below.


// ---------------------------------------------------------------------------
// 3. Does the discontinuity survive a secular trend?               REVIEW §1.3
// ---------------------------------------------------------------------------
gen t = time - 14          // 0 = Nov 2022, the announcement month
label var t "Months since announcement"

// (a) As published: level shift only.
eststo trend0: areg gpda post $assets_o c.totalfte post#c.totalfte ///
    b10.month i.icbid, a(id) cluster(id)

// (b) Level shift on top of a common linear trend.
eststo trend1: areg gpda post c.t $assets_o c.totalfte post#c.totalfte ///
    b10.month i.icbid, a(id) cluster(id)

// (c) Level shift plus a change in slope at the announcement.
eststo trend2: areg gpda post c.t c.post#c.t $assets_o c.totalfte ///
    post#c.totalfte b10.month i.icbid, a(id) cluster(id)

esttab trend0 trend1 trend2, keep(post t post#c.t) ci ///
    mtitle("Level shift" "+ linear trend" "+ slope change")
esttab trend0 trend1 trend2 using tables/trend_sensitivity.rtf, replace ///
    keep(post t post#c.t) ci ///
    mtitle("Level shift" "+ linear trend" "+ slope change")

// Expected: post falls from 2.71 [1.64, 3.78] to 0.30 [-0.94, 1.54] once a
// linear trend of ~0.16/month is allowed. Report this in the paper.


// ---------------------------------------------------------------------------
// 4. Placebo announcements inside the pre-policy period            REVIEW §1.3
// ---------------------------------------------------------------------------
// Estimate on the pre-policy window only, pretending the policy was announced
// at various earlier dates. A well-behaved design finds nothing here.

foreach pm in 645 647 649 {          // ym(2022,3), ym(2022,5), ym(2022,7)
    preserve
    keep if yearmonth <= ym(2022,10)
    gen placebo = yearmonth >= `pm'
    di as txt "=== Placebo announcement: " %tm `pm' " ==="
    areg gpda placebo k_mri k_ct k_us placebo#c.k_mri placebo#c.k_ct ///
        placebo#c.k_us c.totalfte placebo#c.totalfte b10.month i.icbid, ///
        a(id) cluster(id)
    restore
}

// Expected: -0.54, -0.04, +0.03 -- no spurious discontinuities.


// ---------------------------------------------------------------------------
// 5. Sensitivity to the masked small counts                        REVIEW §4
// ---------------------------------------------------------------------------
// Masked cells (1-3 referrals/month) are 37.6% of the analysis sample but only
// 1.4% of total referral volume. Re-run the headline model under alternative
// fills to show the result does not depend on the imputation.
//
// Requires re-importing gpda.csv with a flag for the masked cells, i.e. replace
// the imputation block at the top of analysis.do with:
//
//     gen byte masked = missing(roundedcount)
//     set seed 333
//     replace roundedcount = runiformint(1,3) if masked
//
// then, having built the sample:

foreach v in 1 2 3 {
    gen gpda_`v' = cond(masked, `v', gpda)
    qui: areg gpda_`v' post $assets_o c.totalfte post#c.totalfte ///
        b10.month i.icbid, a(id) cluster(id)
    di as txt "masked := `v':  b = " as res %6.3f _b[post]
}

// And the (bad) alternative of dropping them, for contrast:
qui: areg gpda post $assets_o c.totalfte post#c.totalfte b10.month i.icbid ///
    if !masked, a(id) cluster(id)
di as txt "masked dropped:  b = " as res %6.3f _b[post]

// Expected: 2.713 / 2.715 / 2.717 under the three fills, but 8.240 when the
// masked cells are dropped -- dropping selects on high-volume practice-trust
// pairs and inflates the estimate three-fold.


// ---------------------------------------------------------------------------
// 6. Practice-trust pair fixed effects                             REVIEW §5.3
// ---------------------------------------------------------------------------
// Observations are practice-trust-months, but analysis.do absorbs practice
// intercepts only, so a switch in which trust a practice uses is not separated
// from a change in its total volume. Practices refer to 1.87 trusts on average.

egen pairid = group(gpcode orgcode)
eststo pairfe: areg gpda post $assets_o c.totalfte post#c.totalfte ///
    b10.month i.icbid, a(pairid) cluster(id)
esttab trend0 pairfe, keep(post) ci mtitle("Practice FE" "Practice-trust FE")


// ---------------------------------------------------------------------------
// 7. Regional results as a table, not just a map                   REVIEW §1.6
// ---------------------------------------------------------------------------
// The regional percentage changes currently appear only inside the Figure 2
// image. analysis.do already estimates r1-r7; export them with the percentage
// effects so they can be typeset as Table 2.

esttab r4 r5 r7 r6 r1 r2 r3, replace keep(post) ci stats(N mean perceff) ///
    mtitle("North East and Yorkshire" "North West" "South West" "South East" ///
           "East of England" "London" "Midlands")
esttab r4 r5 r7 r6 r1 r2 r3 using tables/gpda_byregion_ordered.rtf, replace ///
    keep(post) ci stats(N mean perceff) ///
    mtitle("North East and Yorkshire" "North West" "South West" "South East" ///
           "East of England" "London" "Midlands")
