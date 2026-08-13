*! did_pipeline.do
*! Stata pipeline for the BJR Short Communication
*! "More tests, not faster tests: GP direct access to cancer diagnostic
*!  imaging in England, 2018-2023"
*!
*! Written linearly: no user-written programs, no abstraction. Every analysis
*! is a single estimation command against one long panel built in section 02,
*! selected with an -if- condition. Read top to bottom.
*!
*! Counterpart of review/did_analysis.py. Expected results are given as
*! comments above each block; a mismatch means the pipelines have diverged.
*!
*! Requires:
*!     ssc install reghdfe, replace
*!     ssc install ftools, replace
*!     ssc install estout, replace
*!     ssc install coefplot, replace
*!     ssc install csdid, replace
*!     ssc install drdid, replace
*!
*! Run from the repository root:  do stata/did_pipeline.do

clear all
set more off
version 15


* ===========================================================================
* 00. Parameters
* ===========================================================================
cap mkdir "stata"
cap mkdir "stata/dataout"
cap mkdir "stata/tables"
cap mkdir "stata/figures"

* NHS England's guidance names, as the minimum direct access set: chest x-ray,
* CT chest, CT abdomen and pelvis, ultrasound abdomen and pelvis, brain MRI.
* Chest x-ray IS covered and must NOT be used as a control modality.
local announce  = tm(2022m11)   // policy announcement
local seriesend = tm(2023m11)   // December 2023 onward is materially incomplete
local covidlo   = tm(2020m3)    // pandemic disruption
local covidhi   = tm(2021m3)
local refmonth  = tm(2022m10)   // event-study reference month


* ===========================================================================
* 01. Append the financial-year files into a trust-month panel
* ===========================================================================
tempfile master
clear
save `master', replace emptyok

foreach fy in 2018m4-2019m3 2019m4-2020m3 2020m4-2021m3 ///
              2021m4-2022m3 2022m4-2023m3 2023m4-2024m3 {
    display as text "appending `fy'"
    use "data/`fy'.dta", clear
    * the 2018-19 file carries fewer variables than later years; append aligns
    append using `master', force
    save `master', replace
}
use `master', clear

keep if substr(orgcode, 1, 1) == "R"      // NHS trusts, as in the original paper
keep if yearmonth <= `seriesend'          // drop the incomplete tail
isid orgcode yearmonth

egen gp_cov  = rowtotal(gpcdixray gpcdict gpcdimri gpcdiultra2), missing
egen tot_cov = rowtotal(totalcdixray totalcdict totalcdimri totalcdiultra2), missing

* Self-check against the Python build the manuscript used. If this fails the
* two pipelines are not analysing the same data.
assert _N == 9984
quietly levelsof orgcode, local(trusts)
assert `: word count `trusts'' == 160
quietly summarize gp_cov
assert reldif(r(sum), 14027250) < 1e-6
quietly summarize tot_cov
assert reldif(r(sum), 58494255) < 1e-6
display as result _n "Self-check passed: 9,984 trust-months, 160 trusts"

compress
save "stata/dataout/did_master.dta", replace


* ===========================================================================
* 02. Build the long panel: trust x month x modality x referral source
* ===========================================================================
* modality  0 = all covered modalities pooled (counts only)
*           1 = brain MRI
*           2 = CT chest and abdomen/pelvis
*           3 = chest radiography
*           4 = ultrasound abdomen/pelvis
*           5 = ultrasound kidney/bladder  (NOT named in the guidance)
*
* src       1 = GP direct referral            (treated)
*           2 = non-GP referrals = total - GP (control, COUNTS only)
*           3 = all referrals                 (control, WAITS only)
*
* Two comparators are needed because medians cannot be differenced: for counts
* the control is total minus GP, but for waiting times only the GP median and
* the all-referrals median are published. Wait estimates are therefore
* attenuated, because the comparator still contains GP activity.

tempfile long
clear
save `long', replace emptyok

* --- modality 0: the pooled covered aggregate (counts only) ---
use "stata/dataout/did_master.dta", clear
keep orgcode yearmonth gp_cov tot_cov
drop if missing(gp_cov) | missing(tot_cov)
gen double nongp = tot_cov - gp_cov
gen byte modality = 0
preserve
    keep orgcode yearmonth modality gp_cov
    rename gp_cov events
    gen byte src = 1
    gen double medwait = .
    tempfile piece
    save `piece'
restore
keep orgcode yearmonth modality nongp
rename nongp events
gen byte src = 2
gen double medwait = .
append using `piece'
append using `long'
save `long', replace

* --- modalities 1-5: counts and waits ---
local k = 1
foreach m in mri ct xray ultra2 ultra1 {
    if "`m'" == "mri"    local gv gpcdimri
    if "`m'" == "mri"    local tv totalcdimri
    if "`m'" == "mri"    local gw mrtgpcdimri
    if "`m'" == "mri"    local tw mrttotalcdimri
    if "`m'" == "ct"     local gv gpcdict
    if "`m'" == "ct"     local tv totalcdict
    if "`m'" == "ct"     local gw mrtgpcdict
    if "`m'" == "ct"     local tw mrttotalcdict
    if "`m'" == "xray"   local gv gpcdixray
    if "`m'" == "xray"   local tv totalcdixray
    if "`m'" == "xray"   local gw mrtgpcdixray
    if "`m'" == "xray"   local tw mrttotalcdixray
    if "`m'" == "ultra2" local gv gpcdiultra2
    if "`m'" == "ultra2" local tv totalcdiultra2
    if "`m'" == "ultra2" local gw mrtgpcdiultra2
    if "`m'" == "ultra2" local tw mrttotalcdiultra2
    if "`m'" == "ultra1" local gv gpcdiultra1
    if "`m'" == "ultra1" local tv totalcdiultra1
    if "`m'" == "ultra1" local gw mrtgpcdiultra1
    if "`m'" == "ultra1" local tw mrttotalcdiultra1

    * GP series: counts and waits
    use "stata/dataout/did_master.dta", clear
    keep orgcode yearmonth `gv' `gw'
    rename `gv' events
    rename `gw' medwait
    gen byte modality = `k'
    gen byte src = 1
    append using `long'
    save `long', replace

    * non-GP counts
    use "stata/dataout/did_master.dta", clear
    keep orgcode yearmonth `gv' `tv'
    drop if missing(`gv') | missing(`tv')
    gen double events = `tv' - `gv'
    gen double medwait = .
    gen byte modality = `k'
    gen byte src = 2
    keep orgcode yearmonth modality src events medwait
    append using `long'
    save `long', replace

    * all-referral waits
    use "stata/dataout/did_master.dta", clear
    keep orgcode yearmonth `tw'
    rename `tw' medwait
    gen double events = .
    gen byte modality = `k'
    gen byte src = 3
    append using `long'
    save `long', replace

    local ++k
}

use `long', clear
label define modlab 0 "All covered pooled" 1 "Brain MRI" 2 "CT chest/abdomen" ///
                    3 "Chest radiography" 4 "Ultrasound abdomen/pelvis" ///
                    5 "Ultrasound kidney/bladder (comparator)"
label values modality modlab
label define srclab 1 "GP direct" 2 "Non-GP" 3 "All referrals"
label values src srclab

gen byte gp   = (src == 1)
gen byte post = yearmonth >= `announce'
gen byte cm   = month(dofm(yearmonth))
egen cell     = group(orgcode src modality)
gen double lev = ln(events)  if events > 0 & !missing(events)
gen double lwt = ln(medwait) if medwait > 0 & !missing(medwait)
gen double tlin = yearmonth
gen postgp = post * gp
gen tgp    = tlin * gp

* Sample flags for the two counterfactual windows. Diagnostic activity
* collapsed in 2020-21 and recovered through 2021-22, so a pre-period starting
* in 2021 uses a depressed baseline and flatters the comparison. The April 2018
* window is primary; April 2021 is reported as sensitivity.
gen byte s_recovery = yearmonth >= tm(2021m4)
gen byte s_precovid = !inrange(yearmonth, `covidlo', `covidhi')

compress
save "stata/dataout/did_long.dta", replace


* ===========================================================================
* 03. Main DiD, activity in policy-covered modalities  (two-way fixed effects)
* ===========================================================================
* i.cm#c.gp lets seasonality differ between the GP and comparator series, so a
* GP-specific Christmas dip is not read as a policy effect.
*
* Expected (review/did_analysis.py):
*   April 2021 baseline : +14.97%  [ +8.73, +21.57]  p<0.001  N =  8,214
*   April 2018 baseline : +10.41%  [ +5.76, +15.26]  p<0.001  N = 14,617
* Coefficients are log points: percentage change = 100*(exp(b)-1).

use "stata/dataout/did_long.dta", clear

display as txt _n "{hline 78}"
display as txt "3a. Main DiD, April 2021 baseline (sensitivity)"
display as txt "{hline 78}"
reghdfe lev postgp i.cm#c.gp if modality == 0 & src <= 2 & s_recovery, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo main_recovery
display as result "  percentage change = " %6.2f 100*(exp(_b[postgp])-1) "%"

display as txt _n "{hline 78}"
display as txt "3b. Main DiD, April 2018 baseline  [PRIMARY]"
display as txt "{hline 78}"
reghdfe lev postgp i.cm#c.gp if modality == 0 & src <= 2 & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo main_precovid
display as result "  percentage change = " %6.2f 100*(exp(_b[postgp])-1) "%"


* ===========================================================================
* 04. Activity by modality (April 2018 baseline)
* ===========================================================================
* Expected: brain MRI +29.03, CT +14.79, chest x-ray +13.45,
*           ultrasound abdomen/pelvis +6.12,
*           ultrasound kidney/bladder +4.14 (comparator, not significant)

display as txt _n "{hline 78}"
display as txt "4. Activity by modality"
display as txt "{hline 78}"

reghdfe lev postgp i.cm#c.gp if modality == 1 & src <= 2 & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_mri
display as result "  Brain MRI: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lev postgp i.cm#c.gp if modality == 2 & src <= 2 & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_ct
display as result "  CT chest/abdomen: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lev postgp i.cm#c.gp if modality == 3 & src <= 2 & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_xray
display as result "  Chest radiography: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lev postgp i.cm#c.gp if modality == 4 & src <= 2 & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_us2
display as result "  Ultrasound abdomen/pelvis: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lev postgp i.cm#c.gp if modality == 5 & src <= 2 & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_us1
display as result "  Ultrasound kidney/bladder (comparator): " ///
    %6.2f 100*(exp(_b[postgp])-1) "%"


* ===========================================================================
* 05. Waiting times, median days from request to test
* ===========================================================================
* Expected: brain MRI +7.05, CT -1.44, chest x-ray -2.42,
*           ultrasound abdomen/pelvis +2.25, kidney/bladder -3.09,
*           pooled across the four covered modalities +5.86 [-0.04, +12.10]

display as txt _n "{hline 78}"
display as txt "5. Waiting times (median days request to test)"
display as txt "{hline 78}"

reghdfe lwt postgp i.cm#c.gp if modality == 1 & inlist(src,1,3) & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo wait_mri
display as result "  Brain MRI: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lwt postgp i.cm#c.gp if modality == 2 & inlist(src,1,3) & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo wait_ct
display as result "  CT chest/abdomen: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lwt postgp i.cm#c.gp if modality == 3 & inlist(src,1,3) & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo wait_xray
display as result "  Chest radiography: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lwt postgp i.cm#c.gp if modality == 4 & inlist(src,1,3) & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo wait_us2
display as result "  Ultrasound abdomen/pelvis: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe lwt postgp i.cm#c.gp if modality == 5 & inlist(src,1,3) & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo wait_us1
display as result "  Ultrasound kidney/bladder: " %6.2f 100*(exp(_b[postgp])-1) "%"

* Pooled across the four covered modalities: cell already includes modality,
* so stacking them simply adds modality-specific intercepts.
reghdfe lwt postgp i.cm#c.gp ///
    if inlist(modality,1,2,3,4) & inlist(src,1,3) & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo wait_pooled
display as result "  POOLED across covered modalities: " ///
    %6.2f 100*(exp(_b[postgp])-1) "%  p=" %6.4f 2*normal(-abs(_b[postgp]/_se[postgp]))


* ===========================================================================
* 06. Robustness: placebo announcement, and a differential linear trend
* ===========================================================================
* Expected: placebo -1.09% (p=0.68); differential-trend level shift +15.56%
*           [+8.35, +23.25] with a trend of -0.13% per month

display as txt _n "{hline 78}"
display as txt "6. Robustness"
display as txt "{hline 78}"

gen byte placebo   = yearmonth >= tm(2021m11)
gen placebogp = placebo * gp
reghdfe lev placebogp i.cm#c.gp ///
    if modality == 0 & src <= 2 & s_precovid & yearmonth < `announce', ///
    absorb(cell yearmonth) vce(cluster orgcode)
display as result "  Placebo announcement Nov 2021: " ///
    %6.2f 100*(exp(_b[placebogp])-1) "%  p=" ///
    %6.4f 2*normal(-abs(_b[placebogp]/_se[placebogp]))

reghdfe lev postgp tgp i.cm#c.gp if modality == 0 & src <= 2 & s_precovid, ///
    absorb(cell yearmonth) vce(cluster orgcode)
display as result "  Level shift allowing a differential trend: " ///
    %6.2f 100*(exp(_b[postgp])-1) "%"
display as result "  Differential trend per month: " %6.3f 100*(exp(_b[tgp])-1) "%"


* ===========================================================================
* 07. Event study: Callaway and Sant'Anna (2021)
* ===========================================================================
* NOTE ON THE ESTIMATOR. Treatment timing here is COMMON, not staggered: every
* treated series (GP referrals) is treated in November 2022, and the comparator
* series are never treated. The negative-weighting and forbidden-comparison
* problems that motivate Callaway-Sant'Anna over two-way fixed effects
* therefore do not arise in this design, and the two should agree closely.
* What csdid does add here is a clean never-treated comparison group, the
* doubly robust estimator, and uniform confidence bands that account for
* testing many event times at once.
*
* Two practical points:
*   (a) csdid needs consecutive time periods. Dropping the pandemic months
*       leaves a 13-month hole, so time is re-indexed. Post-announcement event
*       times are unaffected because the gap is entirely pre-period, but
*       pre-period event-time labels do not correspond to calendar months.
*       The April 2021 window is contiguous and is used for the figure.
*   (b) csdid carries no calendar-month controls, so GP-specific seasonality
*       shows up as noise in the monthly estimates. Section 07c repeats the
*       estimation on a seasonally adjusted outcome.
*   (c) the panel is mildly unbalanced (a trust with no positive count in a
*       month contributes no row). csdid handles this, but if it objects, add
*       the -long2- option, which anchors every comparison to the period before
*       treatment rather than to the varying base period.
*
* Expected simple aggregation (ATT averaged over post periods):
*   April 2021 window, raw outcome                 approximately +11.4%
*   April 2021 window, seasonally adjusted         approximately  +9.1%
*   April 2018 window, seasonally adjusted         approximately  +9.1%
* compared with the two-way fixed effects estimate of +10.4%.

display as txt _n "{hline 78}"
display as txt "7. Callaway-Sant'Anna event study"
display as txt "{hline 78}"

* --- 07a. contiguous April 2021 window, raw outcome ---
use "stata/dataout/did_long.dta", clear
keep if modality == 0 & src <= 2 & s_recovery & !missing(lev)

gen int tt = yearmonth - tm(2021m4) + 1              // consecutive 1..N
gen int gvar = cond(gp == 1, tm(2022m11) - tm(2021m4) + 1, 0)  // 0 = never treated

csdid lev, ivar(cell) time(tt) gvar(gvar) method(dripw) cluster(orgcode) agg(event)
estat simple
estat event

csdid_plot, style(rspike) ///
    title("GP direct referrals vs never-treated comparator") ///
    ytitle("ATT, log points") xtitle("Months since announcement")
graph export "stata/figures/cs_event_study.png", replace width(2200)

* --- 07b. April 2018 window, raw outcome ---
* Time is re-indexed across the pandemic gap; pre-period event-time labels are
* therefore not calendar months. Post-period estimates are unaffected.
use "stata/dataout/did_long.dta", clear
keep if modality == 0 & src <= 2 & s_precovid & !missing(lev)
egen int tt = group(yearmonth)
quietly summarize tt if yearmonth == tm(2022m11)
local gt = r(min)
gen int gvar = cond(gp == 1, `gt', 0)

csdid lev, ivar(cell) time(tt) gvar(gvar) method(dripw) cluster(orgcode) agg(event)
estat simple

* --- 07c. seasonally adjusted outcome ---
* Seasonal factors are estimated from PRE-announcement months only, separately
* for the GP and comparator series, so the adjustment cannot absorb any part of
* the treatment effect.
use "stata/dataout/did_long.dta", clear
keep if modality == 0 & src <= 2 & s_precovid & !missing(lev)

bysort cell: egen double cellmean = mean(lev)
gen double dev = lev - cellmean
bysort gp cm: egen double sfac = mean(cond(yearmonth < `announce', dev, .))
gen double lev_adj = lev - sfac

egen int tt = group(yearmonth)
quietly summarize tt if yearmonth == tm(2022m11)
local gt = r(min)
gen int gvar = cond(gp == 1, `gt', 0)

csdid lev_adj, ivar(cell) time(tt) gvar(gvar) method(dripw) cluster(orgcode) agg(event)
estat simple
estat event


* ===========================================================================
* 08. Export tables
* ===========================================================================
esttab main_precovid act_mri act_ct act_xray act_us2 act_us1 ///
    using "stata/tables/table1_activity.rtf", replace ///
    keep(postgp) b(3) ci(3) star(* 0.05 ** 0.01 *** 0.001) ///
    mtitle("All covered" "Brain MRI" "CT" "Chest x-ray" "US abdo/pelvis" ///
           "US kidney/bladder") ///
    title("Adjusted change in GP direct referral imaging activity") ///
    addnote("Log points; percentage change = 100*(exp(b)-1). Clustered by trust.")

esttab wait_pooled wait_mri wait_ct wait_xray wait_us2 wait_us1 ///
    using "stata/tables/table1_waits.rtf", replace ///
    keep(postgp) b(3) ci(3) star(* 0.05 ** 0.01 *** 0.001) ///
    mtitle("Pooled" "Brain MRI" "CT" "Chest x-ray" "US abdo/pelvis" ///
           "US kidney/bladder") ///
    title("Adjusted change in median request-to-test waiting time") ///
    addnote("Comparator is all referrals, which includes GP, so estimates are attenuated.")

display as result _n "Done. Tables in stata/tables/, figures in stata/figures/."
