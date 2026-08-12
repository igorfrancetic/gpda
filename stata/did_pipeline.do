*! did_pipeline.do
*! Full Stata pipeline reproducing the BJR Short Communication
*! "More tests, not faster tests: GP direct access to cancer diagnostic
*!  imaging in England, 2018-2023"
*!
*! This is the Stata counterpart of review/did_analysis.py. Both should give
*! the same numbers; the Python version is what the manuscript currently
*! quotes, so run this and reconcile before submitting.
*!
*! Requires: reghdfe, ftools, estout, coefplot
*!     ssc install reghdfe, replace
*!     ssc install ftools, replace
*!     ssc install estout, replace
*!     ssc install coefplot, replace
*!
*! Run from the repository root:  do stata/did_pipeline.do

clear all
set more off
version 15

* ---------------------------------------------------------------------------
* 00. Paths and study parameters
* ---------------------------------------------------------------------------
local datain  "data"
local dataout "stata/dataout"
local tables  "stata/tables"
local figures "stata/figures"
cap mkdir "stata"
cap mkdir "`dataout'"
cap mkdir "`tables'"
cap mkdir "`figures'"

* NHS England names, as the minimum direct access set: chest x-ray, CT chest,
* CT abdomen and pelvis, ultrasound abdomen and pelvis, and brain MRI.
* Chest x-ray IS covered and must NOT be used as a control modality.
local covered_gp  gpcdixray gpcdict gpcdimri gpcdiultra2
local covered_tot totalcdixray totalcdict totalcdimri totalcdiultra2

* Ultrasound kidney/bladder is not named in that minimum set: comparator only.
local comp_gp  gpcdiultra1
local comp_tot totalcdiultra1

local announce = tm(2022m11)   // policy announcement
local seriesend = tm(2023m11)  // Dec 2023 onward is materially incomplete
local covidlo  = tm(2020m3)    // pandemic disruption, dropped from long models
local covidhi  = tm(2021m3)
local refmonth = tm(2022m10)   // event-study reference month


* ---------------------------------------------------------------------------
* 01. Build the trust-month master panel
* ---------------------------------------------------------------------------
tempfile master
clear
save `master', replace emptyok

foreach fy in 2018m4-2019m3 2019m4-2020m3 2020m4-2021m3 ///
              2021m4-2022m3 2022m4-2023m3 2023m4-2024m3 {
    display as text "appending `fy'"
    use "`datain'/`fy'.dta", clear
    * the 2018-19 file carries fewer variables than later years; append aligns
    append using `master', force
    save `master', replace
}
use `master', clear

* NHS trusts only, as in the original paper
keep if substr(orgcode, 1, 1) == "R"

* Drop the incomplete tail. February and March 2024 are structural zeros
* (every trust reports 0, not missing); December 2023 and January 2024 decay.
keep if yearmonth <= `seriesend'

isid orgcode yearmonth

* Aggregates. "missing" so a row is missing only if every component is.
egen gp_cov  = rowtotal(`covered_gp'),  missing
egen tot_cov = rowtotal(`covered_tot'), missing

label var gp_cov  "GP direct referral events, policy-covered modalities"
label var tot_cov "All referral events, policy-covered modalities"

compress
save "`dataout'/did_master.dta", replace

display as result _n "Master panel: " _N " trust-months"
quietly levelsof orgcode, local(trusts)
display as result "Trusts: " `: word count `trusts''

* Self-check against the Python build used for the manuscript. If either of
* these fails the two pipelines are not analysing the same data, and the
* discrepancy must be resolved before trusting any estimate below.
assert _N == 9984
assert `: word count `trusts'' == 160
quietly summarize gp_cov
assert reldif(r(sum), 14027250) < 1e-6
quietly summarize tot_cov
assert reldif(r(sum), 58494255) < 1e-6
display as result "Self-check passed: panel matches review/did_analysis.py" 


* ---------------------------------------------------------------------------
* 02. Program: build the two-series panel and estimate the DiD
* ---------------------------------------------------------------------------
* gpvar   : the GP direct referral series (treated)
* cmpvar  : the total series
* subtract: 1 -> comparator is (total - GP); use for COUNTS
*           0 -> comparator is the total itself; use for MEDIAN WAITS, because
*                medians cannot be differenced. Those estimates are attenuated
*                because the comparator still contains GP activity.
* sample  : "recovery" (April 2021 baseline) or "precovid" (April 2018, COVID
*           year dropped)
* spec    : "main", "trend", "event", or a placebo date as "placebo <tm>"

capture program drop didspec
program define didspec, rclass
    syntax , GPvar(name) CMPvar(name) SUBTRACT(integer) ///
             SAMPLE(string) [SPEC(string) LABel(string)]

    quietly {
        use "${dataout}/did_master.dta", clear

        if "`sample'" == "recovery"  keep if yearmonth >= tm(2021m4)
        if "`sample'" == "precovid"  drop if inrange(yearmonth, ${covidlo}, ${covidhi})
        if "`sample'" == "preonly"   keep if yearmonth < ${announce}

        keep orgcode yearmonth `gpvar' `cmpvar'
        drop if missing(`gpvar') | missing(`cmpvar')

        * comparator series
        if `subtract' == 1  gen double ycmp = `cmpvar' - `gpvar'
        else                gen double ycmp = `cmpvar'

        * stack GP on top of comparator
        preserve
            keep orgcode yearmonth `gpvar'
            rename `gpvar' y
            gen byte gp = 1
            tempfile gpser
            save `gpser'
        restore
        keep orgcode yearmonth ycmp
        rename ycmp y
        gen byte gp = 0
        append using `gpser'

        drop if missing(y) | y <= 0
        gen double ly = ln(y)

        gen byte post = yearmonth >= ${announce}
        if strpos("`spec'", "placebo") {
            local pdate : word 2 of `spec'
            replace post = yearmonth >= `pdate'
        }

        egen cell = group(orgcode gp)          // trust x source fixed effect
        gen cm = month(dofm(yearmonth))        // calendar month, for seasonality
        gen postgp = post * gp
        gen double t = yearmonth               // linear time, in months
        gen double tgp = t * gp

        * i.cm#c.gp lets seasonality differ between GP and comparator series,
        * so a GP-specific Christmas dip is not read as a policy effect.
        if "`spec'" == "event" {
            * month-by-month, reference month omitted; month x GP already spans
            * the seasonality terms, so i.cm#c.gp must NOT be added here
            reghdfe ly ib${refmonth}.yearmonth#c.gp, ///
                absorb(cell yearmonth) vce(cluster orgcode)
        }
        else if "`spec'" == "trend" {
            reghdfe ly postgp tgp i.cm#c.gp, ///
                absorb(cell yearmonth) vce(cluster orgcode)
        }
        else {
            reghdfe ly postgp i.cm#c.gp, ///
                absorb(cell yearmonth) vce(cluster orgcode)
        }
    }

    if "`spec'" != "event" {
        local b   = _b[postgp]
        local se  = _se[postgp]
        local pchg = 100*(exp(`b') - 1)
        local plo  = 100*(exp(`b' - 1.96*`se') - 1)
        local phi  = 100*(exp(`b' + 1.96*`se') - 1)
        local pval = 2*normal(-abs(`b'/`se'))
        display as text %-44s "`label'" as result ///
            %8.2f `pchg' "%  [" %6.2f `plo' ", " %6.2f `phi' "]  p=" %6.4f `pval' ///
            "  N=" %8.0fc e(N)
        return scalar pchg = `pchg'
        return scalar lo = `plo'
        return scalar hi = `phi'
        return scalar p  = `pval'
    }
end

* make the locals visible inside the program
global dataout  "`dataout'"
global announce = `announce'
global covidlo  = `covidlo'
global covidhi  = `covidhi'
global refmonth = `refmonth'


* ---------------------------------------------------------------------------
* 03. Main DiD: activity in policy-covered modalities
* ---------------------------------------------------------------------------
display as txt _n "{hline 88}"
display as txt "1. MAIN DiD - GP direct referrals vs all other referrals"
display as txt "{hline 88}"

* Expected (from review/did_analysis.py):
*   April 2021 baseline : +14.97%  [ +8.73, +21.57]  p<0.001  N =  8,214, 139 trusts
*   April 2018 baseline : +10.41%  [ +5.76, +15.26]  p<0.001  N = 14,617, 154 trusts
didspec, gpvar(gp_cov) cmpvar(tot_cov) subtract(1) sample(recovery) ///
    label("April 2021 baseline (post-COVID recovery)")
eststo main_recovery

didspec, gpvar(gp_cov) cmpvar(tot_cov) subtract(1) sample(precovid) ///
    label("April 2018 baseline, pandemic year dropped  [PRIMARY]")
eststo main_precovid


* ---------------------------------------------------------------------------
* 04. By modality, plus the comparator the guidance does not name
* ---------------------------------------------------------------------------
display as txt _n "{hline 88}"
display as txt "2. BY MODALITY (April 2018 baseline)"
display as txt "{hline 88}"
* Expected: brain MRI +29.03, CT +14.79, chest x-ray +13.45,
*           US abdo/pelvis +6.12, US kidney/bladder +4.14 (comparator, ns)

local mods   gpcdimri  gpcdict            gpcdixray          gpcdiultra2                gpcdiultra1
local totmod totalcdimri totalcdict       totalcdixray       totalcdiultra2             totalcdiultra1
local modlab "Brain MRI" "CT chest/abdomen" "Chest radiography" "Ultrasound abdomen/pelvis" "Ultrasound kidney/bladder (comparator)"

local i = 1
foreach m of local mods {
    local tm : word `i' of `totmod'
    local lb : word `i' of `modlab'
    didspec, gpvar(`m') cmpvar(`tm') subtract(1) sample(precovid) label("`lb'")
    eststo mod_`i'
    local ++i
}


* ---------------------------------------------------------------------------
* 05. Waiting times: median days from request to test
* ---------------------------------------------------------------------------
* NOTE subtract(0): the DID publishes medians for GP referrals and for ALL
* referrals, but not for non-GP referrals separately. Medians cannot be
* differenced, so the comparator retains GP activity and these estimates are
* attenuated towards zero.
display as txt _n "{hline 88}"
display as txt "3. WAITING TIMES (median days request to test)"
display as txt "{hline 88}"
* Expected: brain MRI +7.05, CT -1.44, chest x-ray -2.42, US abdo/pelvis +2.25,
*           US kidney/bladder -3.09; pooled +5.86 [-0.04, +12.10] p=0.052

local wgp   mrtgpcdimri     mrtgpcdict       mrtgpcdixray       mrtgpcdiultra2    mrtgpcdiultra1
local wtot  mrttotalcdimri  mrttotalcdict    mrttotalcdixray    mrttotalcdiultra2 mrttotalcdiultra1

local i = 1
foreach w of local wgp {
    local tw : word `i' of `wtot'
    local lb : word `i' of `modlab'
    didspec, gpvar(`w') cmpvar(`tw') subtract(0) sample(precovid) label("`lb'")
    eststo wait_`i'
    local ++i
}

* Pooled across the four covered modalities: stack modality-level medians and
* absorb trust x source x modality.
display as txt _n "  Pooled across the four covered modalities:"
quietly {
    tempfile pooled
    clear
    save `pooled', replace emptyok

    local k = 1
    foreach pair in "mrtgpcdimri mrttotalcdimri" "mrtgpcdict mrttotalcdict" ///
                    "mrtgpcdixray mrttotalcdixray" "mrtgpcdiultra2 mrttotalcdiultra2" {
        local g : word 1 of `pair'
        local a : word 2 of `pair'
        use "`dataout'/did_master.dta", clear
        drop if inrange(yearmonth, `covidlo', `covidhi')
        keep orgcode yearmonth `g' `a'
        drop if missing(`g') | missing(`a')
        gen byte modality = `k'
        preserve
            keep orgcode yearmonth modality `g'
            rename `g' y
            gen byte gp = 1
            tempfile tg
            save `tg'
        restore
        keep orgcode yearmonth modality `a'
        rename `a' y
        gen byte gp = 0
        append using `tg'
        append using `pooled'
        save `pooled', replace
        local ++k
    }

    use `pooled', clear
    drop if missing(y) | y <= 0
    gen double ly = ln(y)
    gen byte post = yearmonth >= `announce'
    egen cell = group(orgcode gp modality)
    gen cm = month(dofm(yearmonth))
    gen postgp = post*gp
    reghdfe ly postgp i.cm#c.gp, absorb(cell yearmonth) vce(cluster orgcode)
}
local b = _b[postgp]
local se = _se[postgp]
display as text %-44s "  All covered modalities pooled" as result ///
    %8.2f 100*(exp(`b')-1) "%  [" %6.2f 100*(exp(`b'-1.96*`se')-1) ", " ///
    %6.2f 100*(exp(`b'+1.96*`se')-1) "]  p=" %6.4f 2*normal(-abs(`b'/`se'))


* ---------------------------------------------------------------------------
* 06. Robustness
* ---------------------------------------------------------------------------
display as txt _n "{hline 88}"
display as txt "4. ROBUSTNESS"
display as txt "{hline 88}"

* Expected: placebo -1.09% (p=0.68); level shift with trend +15.56%
*           [+8.35, +23.25]; differential trend -0.13% per month

* (a) placebo announcement inside the pre-policy period
didspec, gpvar(gp_cov) cmpvar(tot_cov) subtract(1) sample(preonly) ///
    spec("placebo `=tm(2021m11)'") label("Placebo announcement Nov 2021 (pre-period only)")

* (b) allow a differential linear trend between the two series
didspec, gpvar(gp_cov) cmpvar(tot_cov) subtract(1) sample(precovid) ///
    spec("trend") label("Level shift, allowing a differential linear trend")
display as text "     differential trend per month: " as result ///
    %6.3f 100*(exp(_b[tgp])-1) "%"


* ---------------------------------------------------------------------------
* 07. Event study and figure
* ---------------------------------------------------------------------------
display as txt _n "{hline 88}"
display as txt "5. EVENT STUDY (reference month October 2022)"
display as txt "{hline 88}"

didspec, gpvar(gp_cov) cmpvar(tot_cov) subtract(1) sample(recovery) spec("event")
eststo eventstudy

* Note: coefplot indexes the x axis by coefficient position, not by calendar
* month, so no vertical announcement line is drawn; October 2022 is the omitted
* reference and November 2022 is the first post-announcement point.
coefplot eventstudy, vertical keep(*yearmonth#c.gp) omitted baselevels ///
    yline(0, lcolor(gs8)) ///
    xlabel(, angle(45) labsize(vsmall)) ///
    ytitle("Log difference, GP vs other referrals") ///
    xtitle("Month") ///
    note("Reference month October 2022. 95% confidence intervals, clustered by trust.")
graph export "`figures'/event_study.png", replace width(2100)


* ---------------------------------------------------------------------------
* 08. Export the main table
* ---------------------------------------------------------------------------
esttab main_precovid mod_1 mod_2 mod_3 mod_4 mod_5 ///
    using "`tables'/table1_activity.rtf", replace ///
    keep(postgp) b(3) ci(3) star(* 0.05 ** 0.01 *** 0.001) ///
    mtitle("All covered" "Brain MRI" "CT" "Chest x-ray" "US abdo/pelvis" "US kidney/bladder") ///
    title("Adjusted change in GP direct referral imaging activity") ///
    addnote("Log-linear DiD. Coefficients are log points; exponentiate for percentage change.")

esttab wait_1 wait_2 wait_3 wait_4 wait_5 ///
    using "`tables'/table1_waits.rtf", replace ///
    keep(postgp) b(3) ci(3) star(* 0.05 ** 0.01 *** 0.001) ///
    mtitle("Brain MRI" "CT" "Chest x-ray" "US abdo/pelvis" "US kidney/bladder") ///
    title("Adjusted change in median request-to-test waiting time")

display as result _n "Done. Tables in `tables'/, figure in `figures'/."
