*! did_pipeline.do
*! Complete, self-contained Stata pipeline for the BJR Short Communication
*! "More tests, not faster tests: GP direct access to cancer diagnostic
*!  imaging in England, 2018-2025"
*!
*! Runs end to end from the raw published spreadsheets in datain/. Nothing
*! else is required: it imports the NHS England Diagnostic Imaging Dataset
*! tables, builds the panel, estimates every model in the paper, and writes
*! the tables and figures.
*!
*! Written linearly: no user-written programs. After the panel is built in
*! section 02, every analysis is a single estimation command selected with an
*! -if- condition. Read top to bottom.
*!
*! DESIGN. GP direct referrals are the treated series; referrals from all
*! other sources to the SAME trust, in the SAME test group and month, are the
*! control. Source setting is published as "All" and "GP Direct Access", so
*! for counts the control is All minus GP. Medians cannot be differenced, so
*! for waiting times the comparator is the All median, which still contains GP
*! activity and therefore attenuates those estimates towards zero.
*!
*! ESTIMATOR. Two-way fixed effects is primary (sections 03-06). Treatment
*! timing is common rather than staggered and the comparator series are never
*! treated, so TWFE recovers the ATT without the weighting problems of
*! staggered adoption, and it admits GP-specific calendar-month controls,
*! which matters because seasonality is the dominant nuisance here.
*! Callaway-Sant'Anna (section 08) is a robustness check, not the headline.
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
set varabbrev off
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
* Chest x-ray IS covered and must NOT be used as a control test group.
* Ultrasound of the kidney or bladder is NOT named, and serves as a comparator.
local announce = tm(2022m11)   // policy announcement
local covidlo  = tm(2020m3)    // pandemic disruption, dropped from all models
local covidhi  = tm(2021m3)
local refmonth = tm(2022m10)   // event-study reference month
local truncate = tm(2023m11)   // earlier cut-off, reported as sensitivity


* ===========================================================================
* 01. Import the published DID tables
* ===========================================================================
* Table 4 = counts, Table 5 = median days request to test, for the groups of
* tests suitable for diagnosing cancer, by body site, provider, month and
* source setting.
*
* The header row is not in a fixed position: Table 4 uses row 13 throughout,
* Table 5 uses row 14 except in 2022-23 where it uses row 13. Everything below
* is therefore located by content, never by position. Sheets are imported as
* strings so the header row can be read before anything is destrung.

tempfile raw
clear
save `raw', replace emptyok

foreach folder in 2018_19 2019_20 2020_21 2021_22 2022_23 2023_24 2024-25 {

    * financial year start, from the folder name
    local fystart = real(substr("`folder'", 1, 4))

    foreach tbl in 4 5 {
        if `tbl' == 4  local vname events
        if `tbl' == 5  local vname wait

        local files : dir "datain/raw_trust/`folder'" files "DID-Table-`tbl'-*.xlsx"
        foreach f of local files {
            display as text "  `folder'  Table `tbl'  `f'"
            import excel using "datain/raw_trust/`folder'/`f'", ///
                sheet("Provider") allstring clear

            * ---- locate the header row: the one carrying "Org Code" ----
            gen long _row = _n
            gen byte _hdr = 0
            foreach v of varlist _all {
                capture confirm string variable `v'
                if !_rc  quietly replace _hdr = 1 if `v' == "Org Code"
            }
            quietly summarize _row if _hdr == 1
            local hr = r(min)
            if missing("`hr'") {
                display as error "  no header row in `f' -- skipped"
                continue
            }

            * ---- map column letters to fields, from that header row ----
            local vreg ""
            local vcode ""
            local vtest ""
            local vsrc ""
            foreach m in Apr May Jun Jul Aug Sep Oct Nov Dec Jan Feb Mar {
                local col`m' ""
            }
            foreach v of varlist _all {
                capture confirm string variable `v'
                if _rc  continue
                local val = `v'[`hr']
                if "`val'" == "Region"          local vreg  `v'
                if "`val'" == "Org Code"        local vcode `v'
                if "`val'" == "Test"            local vtest `v'
                if "`val'" == "Source setting"  local vsrc  `v'
                foreach m in Apr May Jun Jul Aug Sep Oct Nov Dec Jan Feb Mar {
                    if "`val'" == "`m'"  local col`m' `v'
                }
            }

            keep if _row > `hr'
            keep `vreg' `vcode' `vtest' `vsrc' ///
                 `colApr' `colMay' `colJun' `colJul' `colAug' `colSep' ///
                 `colOct' `colNov' `colDec' `colJan' `colFeb' `colMar'

            rename `vreg'  regioncode
            rename `vcode' orgcode
            rename `vtest' test
            rename `vsrc'  src
            foreach m in Apr May Jun Jul Aug Sep Oct Nov Dec Jan Feb Mar {
                rename `col`m'' v`m'
                quietly destring v`m', replace force
            }

            * the "-" org code rows are the ENGLAND totals
            drop if orgcode == "-" | orgcode == "" | missing(orgcode)

            * ---- wide months to long ----
            gen long _id = _n
            reshape long v, i(_id) j(mon) string
            rename v `vname'
            drop if missing(`vname')

            gen int monthnum = .
            local k = 1
            foreach m in Apr May Jun Jul Aug Sep Oct Nov Dec Jan Feb Mar {
                local cal = cond(`k' <= 9, `k' + 3, `k' - 9)
                quietly replace monthnum = `cal' if mon == "`m'"
                local ++k
            }
            gen int yr = cond(monthnum >= 4, `fystart', `fystart' + 1)
            gen yearmonth = ym(yr, monthnum)
            format yearmonth %tm

            keep regioncode orgcode test src yearmonth `vname'
            append using `raw'
            save `raw', replace
        }
    }
}

use `raw', clear
* one row per trust-test-source-month, with counts and waits side by side
collapse (firstnm) regioncode (max) events wait, by(orgcode test src yearmonth)
keep if substr(orgcode, 1, 1) == "R"          // NHS trusts only
compress
save "stata/dataout/did_panel_long.dta", replace

display as result _n "Imported panel:"
quietly levelsof orgcode, local(tr)
display as result "  trusts: " `: word count `tr''
quietly summarize yearmonth
display as result "  months: " %tm r(min) " to " %tm r(max)


* ===========================================================================
* 02. Build the estimation panel: GP series stacked on its comparator
* ===========================================================================
use "stata/dataout/did_panel_long.dta", clear

gen byte covered = inlist(test, "Chest (X-ray)", "Chest and/or abdomen (CT)", ///
                                "Brain (MRI)", "Abdomen and/or pelvis (Ultrasound)")
gen byte comparator = (test == "Kidney or Bladder (Ultrasound)")
keep if covered | comparator

gen byte grp = .
replace grp = 1 if test == "Brain (MRI)"
replace grp = 2 if test == "Chest and/or abdomen (CT)"
replace grp = 3 if test == "Chest (X-ray)"
replace grp = 4 if test == "Abdomen and/or pelvis (Ultrasound)"
replace grp = 5 if comparator
label define grplab 0 "All covered pooled" 1 "Brain MRI" 2 "CT chest/abdomen" ///
                    3 "Chest radiography" 4 "Ultrasound abdomen/pelvis" ///
                    5 "Ultrasound kidney/bladder (comparator)"

* ---- counts: GP, and non-GP = All minus GP ----
preserve
    keep orgcode regioncode grp yearmonth src events
    drop if missing(events)
    gen str5 srctag = cond(src == "GP Direct Access", "gp", "all")
    drop src
    reshape wide events, i(orgcode regioncode grp yearmonth) j(srctag) string
    rename eventsall ev_all
    rename eventsgp ev_gp
    gen double ev_nongp = ev_all - ev_gp
    keep orgcode regioncode grp yearmonth ev_gp ev_nongp
    reshape long ev_, i(orgcode regioncode grp yearmonth) j(who) string
    rename ev_ y
    gen byte gp = (who == "gp")
    gen byte outcome = 1                       // 1 = activity
    drop who
    tempfile counts
    save `counts'
restore

* ---- waits: GP median, and the All median as comparator ----
keep orgcode regioncode grp yearmonth src wait
drop if missing(wait)
gen byte gp = (src == "GP Direct Access")
rename wait y
gen byte outcome = 2                           // 2 = median wait
keep orgcode regioncode grp yearmonth y gp outcome
append using `counts'

drop if missing(y) | y <= 0
gen double ly = ln(y)

* pooled covered aggregate for the activity models
preserve
    keep if outcome == 1 & inrange(grp, 1, 4)
    collapse (sum) y, by(orgcode regioncode yearmonth gp outcome)
    gen byte grp = 0
    gen double ly = ln(y)
    tempfile pooled
    save `pooled'
restore
append using `pooled'
label values grp grplab

gen byte post = yearmonth >= `announce'
gen byte cm   = month(dofm(yearmonth))
gen double tlin = yearmonth
egen cell = group(orgcode gp grp outcome)      // trust x source x group x outcome
gen postgp = post * gp
gen tgp    = tlin * gp

* pandemic disruption is dropped from every model
gen byte insample = !inrange(yearmonth, `covidlo', `covidhi')

* NHS England region names, for the community diagnostic centre merge
gen region = ""
replace region = "London"                   if regioncode == "Y56"
replace region = "South West"               if regioncode == "Y58"
replace region = "South East"               if regioncode == "Y59"
replace region = "Midlands"                 if regioncode == "Y60"
replace region = "East of England"          if regioncode == "Y61"
replace region = "North West"               if regioncode == "Y62"
replace region = "North East and Yorkshire" if regioncode == "Y63"

compress
save "stata/dataout/did_analysis.dta", replace


* ===========================================================================
* 03. Main difference-in-differences: activity
* ===========================================================================
* i.cm#c.gp lets seasonality differ between the GP and comparator series, so a
* GP-specific Christmas dip is not read as a policy effect.
*
* Expected: +10.07%  [+5.07, +15.32]  p<0.001
* Coefficients are log points: percentage change = 100*(exp(b)-1).

use "stata/dataout/did_analysis.dta", clear

display as txt _n "{hline 78}"
display as txt "3. MAIN DiD - activity, all covered test groups (PRIMARY RESULT)"
display as txt "{hline 78}"
reghdfe ly postgp i.cm#c.gp if grp == 0 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_all
display as result "  percentage change = " %6.2f 100*(exp(_b[postgp])-1) "%"


* ===========================================================================
* 04. Activity by test group
* ===========================================================================
* Expected: brain MRI +35.24, CT +14.86, chest x-ray +12.94,
*           ultrasound abdomen/pelvis +7.10,
*           ultrasound kidney/bladder +8.23 (comparator, not significant)

display as txt _n "{hline 78}"
display as txt "4. Activity by test group"
display as txt "{hline 78}"

reghdfe ly postgp i.cm#c.gp if grp == 1 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_mri
display as result "  Brain MRI: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe ly postgp i.cm#c.gp if grp == 2 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_ct
display as result "  CT chest/abdomen: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe ly postgp i.cm#c.gp if grp == 3 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_xray
display as result "  Chest radiography: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe ly postgp i.cm#c.gp if grp == 4 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_us2
display as result "  Ultrasound abdomen/pelvis: " %6.2f 100*(exp(_b[postgp])-1) "%"

reghdfe ly postgp i.cm#c.gp if grp == 5 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo act_us1
display as result "  Ultrasound kidney/bladder (comparator): " ///
    %6.2f 100*(exp(_b[postgp])-1) "%"


* ===========================================================================
* 05. Waiting times, median days from request to test
* ===========================================================================
* The comparator is the All-referrals median, which still contains GP
* activity, so these estimates are attenuated towards zero.
*
* Expected: pooled +3.08 [-1.84, 8.25] p=0.22; brain MRI +3.94, CT -6.40,
*           chest x-ray -8.69, ultrasound abdomen/pelvis -2.33,
*           kidney/bladder -10.23. None significant at 5%.

display as txt _n "{hline 78}"
display as txt "5. Waiting times (median days request to test)"
display as txt "{hline 78}"

reghdfe ly postgp i.cm#c.gp if inrange(grp,1,4) & outcome == 2 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
eststo wait_all
display as result "  POOLED across covered groups: " ///
    %6.2f 100*(exp(_b[postgp])-1) "%  p=" %6.4f 2*normal(-abs(_b[postgp]/_se[postgp]))

forvalues g = 1/5 {
    reghdfe ly postgp i.cm#c.gp if grp == `g' & outcome == 2 & insample, ///
        absorb(cell yearmonth) vce(cluster orgcode)
    eststo wait_`g'
    display as result "  group `g': " %6.2f 100*(exp(_b[postgp])-1) "%"
}


* ===========================================================================
* 06. Robustness: placebo, differential trend, earlier cut-off
* ===========================================================================
* Expected: placebo -1.05% (p=0.69); with a differential trend +16.84%
*           [+9.13, +25.10] and a trend of -0.141% per month; truncating the
*           series at November 2023 gives +10.66% [+6.17, +15.35].

display as txt _n "{hline 78}"
display as txt "6. Robustness"
display as txt "{hline 78}"

gen byte placebo = yearmonth >= tm(2021m11)
gen placebogp = placebo * gp
reghdfe ly placebogp i.cm#c.gp ///
    if grp == 0 & outcome == 1 & insample & yearmonth < `announce', ///
    absorb(cell yearmonth) vce(cluster orgcode)
display as result "  Placebo announcement Nov 2021: " ///
    %6.2f 100*(exp(_b[placebogp])-1) "%  p=" ///
    %6.4f 2*normal(-abs(_b[placebogp]/_se[placebogp]))

reghdfe ly postgp tgp i.cm#c.gp if grp == 0 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
display as result "  Allowing a differential trend: " %6.2f 100*(exp(_b[postgp])-1) "%"
display as result "    differential trend per month: " %6.3f 100*(exp(_b[tgp])-1) "%"

reghdfe ly postgp i.cm#c.gp ///
    if grp == 0 & outcome == 1 & insample & yearmonth <= `truncate', ///
    absorb(cell yearmonth) vce(cluster orgcode)
display as result "  Truncated at Nov 2023: " %6.2f 100*(exp(_b[postgp])-1) "%"


* ===========================================================================
* 07. Community diagnostic centres as a competing explanation
* ===========================================================================
* Sivey and Wen (2024) show CDCs raised diagnostic volume with no effect on
* waiting times, which makes them the obvious confounder. Two things answer it.
*
* Timing: all 79 dated first-wave CDCs opened between July 2021 and August
* 2022, every one before the announcement, so they cannot generate a step at
* it. Direct test: regional CDC exposure leaves the estimate intact.
*
* Expected: announcement +13.50% [+5.51, +22.10] once exposure is included,
*           exposure itself -2.14% (p=0.21).

display as txt _n "{hline 78}"
display as txt "7. Community diagnostic centre exposure"
display as txt "{hline 78}"

preserve
    import delimited "datain/cdc/cdc_operational_2022-08-14.tsv", ///
        delimiter(tab) varnames(1) clear stringcols(_all)
    gen livedate = date(live_date, "DMY")           // "HUB" rows become missing
    drop if missing(livedate)
    gen cdcmonth = mofd(livedate)
    keep region cdcmonth
    tempfile cdc
    save `cdc'
restore

* cumulative CDCs live in each region by month
preserve
    use `cdc', clear
    gen n = 1
    collapse (sum) opened = n, by(region cdcmonth)
    rename cdcmonth yearmonth
    tempfile opencount
    save `opencount'
restore

merge m:1 region yearmonth using `opencount', keep(master match) nogenerate
replace opened = 0 if missing(opened)
sort region yearmonth
by region: gen double ncdc = sum(opened) if !missing(region)
quietly summarize ncdc
gen double ncdc_z = (ncdc - r(mean)) / r(sd)
gen cdcgp = ncdc_z * gp

reghdfe ly postgp cdcgp i.cm#c.gp if grp == 0 & outcome == 1 & insample, ///
    absorb(cell yearmonth) vce(cluster orgcode)
display as result "  Announcement: " %6.2f 100*(exp(_b[postgp])-1) "%"
display as result "  CDC exposure (per SD): " %6.2f 100*(exp(_b[cdcgp])-1) ///
    "%  p=" %6.4f 2*normal(-abs(_b[cdcgp]/_se[cdcgp]))


* ===========================================================================
* 08. Robustness: Callaway and Sant'Anna (2021) event study
* ===========================================================================
* Confirms section 03; it is not the headline. Treatment timing is common and
* the comparator series are never treated, so the negative-weighting problem
* that motivates this estimator does not arise. csdid carries no
* calendar-month controls, so GP-specific seasonality shows up as noise in the
* monthly estimates; section 08b repeats it on a seasonally adjusted outcome.
*
* csdid needs consecutive periods. Dropping the pandemic leaves a gap, so time
* is re-indexed; post-announcement event times are unaffected because the gap
* is entirely pre-period.

display as txt _n "{hline 78}"
display as txt "8. ROBUSTNESS: Callaway-Sant'Anna"
display as txt "{hline 78}"

preserve
    keep if grp == 0 & outcome == 1 & insample
    egen int tt = group(yearmonth)
    quietly summarize tt if yearmonth == `announce'
    local gt = r(min)
    gen int gvar = cond(gp == 1, `gt', 0)      // 0 = never treated
    egen int unit = group(orgcode gp)

    csdid ly, ivar(unit) time(tt) gvar(gvar) method(dripw) ///
        cluster(orgcode) agg(event)
    estat simple

    * --- 08b. seasonally adjusted, factors from pre-announcement months only
    bysort unit: egen double unitmean = mean(ly)
    gen double dev = ly - unitmean
    gen double devpre = dev if yearmonth < `announce'
    bysort gp cm: egen double sfac = mean(devpre)
    gen double ly_adj = ly - sfac

    csdid ly_adj, ivar(unit) time(tt) gvar(gvar) method(dripw) ///
        cluster(orgcode) agg(event)
    estat simple
    estat event

    csdid_plot, style(rspike) ///
        title("GP direct referrals vs never-treated comparator") ///
        ytitle("ATT, log points") xtitle("Months since announcement")
    graph export "stata/figures/cs_event_study.png", replace width(2200)
restore


* ===========================================================================
* 09. Export tables
* ===========================================================================
esttab act_all act_mri act_ct act_xray act_us2 act_us1 ///
    using "stata/tables/table1_activity.rtf", replace ///
    keep(postgp) b(3) ci(3) star(* 0.05 ** 0.01 *** 0.001) ///
    mtitle("All covered" "Brain MRI" "CT" "Chest x-ray" "US abdo/pelvis" ///
           "US kidney/bladder") ///
    title("Adjusted change in GP direct referral imaging activity") ///
    addnote("Log points; percentage change = 100*(exp(b)-1). Clustered by trust.")

esttab wait_all wait_1 wait_2 wait_3 wait_4 wait_5 ///
    using "stata/tables/table1_waits.rtf", replace ///
    keep(postgp) b(3) ci(3) star(* 0.05 ** 0.01 *** 0.001) ///
    mtitle("Pooled" "Brain MRI" "CT" "Chest x-ray" "US abdo/pelvis" ///
           "US kidney/bladder") ///
    title("Adjusted change in median request-to-test waiting time") ///
    addnote("Comparator is all referrals, which includes GP, so estimates are attenuated.")

display as result _n "Done. Tables in stata/tables/, figures in stata/figures/."
