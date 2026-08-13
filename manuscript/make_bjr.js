const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell,
        WidthType, ShadingType, ImageRun, PageBreak } = require('docx');

const W = 9360;
const F = 'Calibri';

const p = (text, o = {}) => new Paragraph({
  spacing: { after: o.after === undefined ? 150 : o.after, line: o.line || 300 },
  alignment: o.align || AlignmentType.LEFT,
  indent: o.indent,
  children: [new TextRun({ text, bold: o.bold, italics: o.italics, size: o.size || 22, font: F })]
});

const runs = (parts, o = {}) => new Paragraph({
  spacing: { after: o.after === undefined ? 150 : o.after, line: o.line || 300 },
  children: parts.map(x => new TextRun({
    text: x.t, bold: x.b, italics: x.i, superScript: x.sup, size: x.size || o.size || 22, font: F }))
});

const h = (text, size = 26) => new Paragraph({
  spacing: { before: 300, after: 130 },
  children: [new TextRun({ text, bold: true, size, font: F })]
});

const cell = (text, o = {}) => new TableCell({
  width: { size: o.w, type: WidthType.DXA },
  columnSpan: o.span,
  shading: o.shade ? { type: ShadingType.CLEAR, fill: o.shade, color: 'auto' } : undefined,
  margins: { top: 60, bottom: 60, left: 90, right: 90 },
  children: [new Paragraph({
    spacing: { after: 0, line: 240 },
    alignment: o.align || AlignmentType.LEFT,
    children: [new TextRun({ text, bold: o.b, italics: o.i, size: o.size || 18, font: F })] })]
});

const ref = (n, t) => new Paragraph({
  spacing: { after: 80, line: 240 }, indent: { left: 400, hanging: 400 },
  children: [new TextRun({ text: `${n}. ${t}`, size: 18, font: F })]
});

const img = (file, w, hgt) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 120, after: 100 },
  children: [new ImageRun({ type: 'png', data: fs.readFileSync(file), transformation: { width: w, height: hgt } })]
});

// ---------------- Table 1 ----------------
const TW = [2500, 1750, 1600, 1750, 1760];
const row = (c, o = {}) => new TableRow({ children: c.map((t, i) =>
  cell(t, { w: TW[i], b: o.b, i: o.i, shade: o.shade, align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER })) });

const t1 = new Table({
  columnWidths: TW, width: { size: W, type: WidthType.DXA },
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell('', { w: TW[0], shade: 'E8EEF4' }),
      cell('Imaging activity', { w: TW[1] + TW[2], span: 2, b: true, shade: 'E8EEF4', align: AlignmentType.CENTER }),
      cell('Median wait, request to test', { w: TW[3] + TW[4], span: 2, b: true, shade: 'E8EEF4', align: AlignmentType.CENTER })
    ] }),
    new TableRow({ children: [
      cell('Modality', { w: TW[0], b: true, shade: 'F4F6F8' }),
      cell('% change', { w: TW[1], b: true, shade: 'F4F6F8', align: AlignmentType.CENTER }),
      cell('95% CI', { w: TW[2], b: true, shade: 'F4F6F8', align: AlignmentType.CENTER }),
      cell('% change', { w: TW[3], b: true, shade: 'F4F6F8', align: AlignmentType.CENTER }),
      cell('95% CI', { w: TW[4], b: true, shade: 'F4F6F8', align: AlignmentType.CENTER })
    ] }),
    row(['All covered test groups', '+10.1', '5.1 to 15.3', '+3.1', '−1.8 to 8.3'], { b: true }),
    row(['Brain MRI', '+35.2', '24.7 to 46.7', '+3.9', '−4.2 to 12.7']),
    row(['CT chest and abdomen/pelvis', '+14.9', '6.6 to 23.8', '−6.4', '−13.1 to 0.9']),
    row(['Chest radiography', '+12.9', '8.5 to 17.6', '−8.7', '−29.2 to 17.7']),
    row(['Ultrasound abdomen/pelvis', '+7.1', '−0.2 to 15.0', '−2.3', '−9.8 to 5.7']),
    new TableRow({ children: [cell('Comparator not named in the guidance', { w: W, span: 5, i: true, shade: 'F4F6F8' })] }),
    row(['Ultrasound kidney/bladder', '+8.2', '−4.6 to 22.8', '−10.2', '−19.8 to 0.4'])
  ]
});

const doc = new Document({
  creator: 'Igor Francetic',
  title: 'GP direct access to cancer imaging in England: more tests, not faster tests',
  styles: { default: { document: { run: { font: F, size: 22 } } } },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    children: [
      new Paragraph({ spacing: { after: 200 }, children: [new TextRun({
        text: 'More tests, not faster tests: GP direct access to cancer diagnostic imaging in England, 2018–2025',
        bold: true, size: 30, font: F })] }),
      runs([{ t: 'Igor Francetic' }, { t: '1,2', sup: true }, { t: ', Sam WD Merriel' }, { t: '1', sup: true },
            { t: ', Stephen Bradley' }, { t: '3', sup: true }], { after: 120 }),
      runs([{ t: '1 ', sup: true, size: 18 }, { t: 'Centre for Primary Care and Health Services Research, The University of Manchester, Manchester, UK', size: 18 }], { after: 40 }),
      runs([{ t: '2 ', sup: true, size: 18 }, { t: 'Competence Centre for Healthcare Practices and Policies, University of Applied Sciences and Arts of Southern Switzerland, Manno, Switzerland', size: 18 }], { after: 40 }),
      runs([{ t: '3 ', sup: true, size: 18 }, { t: 'University of Sheffield, Sheffield, UK', size: 18 }], { after: 60 }),
      runs([{ t: 'Corresponding author: ', b: true, size: 18 }, { t: 'Igor Francetic, igor.francetic@manchester.ac.uk', size: 18 }], { after: 60 }),
      runs([{ t: 'Article type: ', b: true, size: 18 }, { t: 'Short Communication.  ', size: 18 },
            { t: 'Word count (main text): ', b: true, size: 18 }, { t: 'approximately 1,600.', size: 18 }], { after: 280 }),

      h('Abstract'),
      runs([{ t: 'Objectives. ', b: true }, { t: 'NHS England’s GP Direct Access policy, announced in November 2022, gave general practitioners direct access to chest radiography, CT, ultrasound and brain MRI for patients with symptoms below the threshold for an urgent suspected cancer referral. We assessed whether it changed the volume and timeliness of GP-requested cancer-detection imaging.' }], { after: 100 }),
      runs([{ t: 'Methods. ', b: true }, { t: 'Monthly Diagnostic Imaging Dataset returns from 160 English NHS trusts, April 2018 to March 2025, excluding the pandemic disruption, giving 29 post-announcement months. We used a difference-in-differences design comparing GP direct referrals with all other referrals at the same trust, test group and month, with trust-by-source and calendar-time fixed effects, GP-specific seasonality, and errors clustered by trust.' }], { after: 100 }),
      runs([{ t: 'Results. ', b: true }, { t: 'GP direct referrals in covered modalities rose 10.1% relative to other referrals (95% CI 5.1 to 15.3, p<0.001), most for brain MRI (35.2%) and CT (14.9%). No covered modality showed a statistically significant change in median request-to-test waiting time; pooled across modalities the change was +3.1% (95% CI −1.8 to 8.3, p=0.22).' }], { after: 100 }),
      runs([{ t: 'Conclusions. ', b: true }, { t: 'Over nearly three years the policy was followed by a sustained increase in GP-requested cancer imaging but no improvement in the waiting times it was intended to reduce.' }], { after: 160 }),

      h('Advances in knowledge', 24),
      p('• Using non-GP referrals to the same trust as a contemporaneous control, GP direct access imaging for cancer detection rose by about 10% after the November 2022 policy and remained elevated for 29 months, concentrated in brain MRI and CT.', { after: 70 }),
      p('• Median waiting time from request to test did not fall in any covered modality, and the pooled change was indistinguishable from zero.', { after: 70 }),
      p('• Expanding access without matching diagnostic capacity increased activity without improving timeliness, which is directly relevant to how future direct access pathways are resourced.', { after: 200 }),

      h('Introduction'),
      p('The NHS Long Term Plan set an aim to diagnose 75% of new cancers in England at an early stage by 2028 (1). To support that aim, NHS England announced in November 2022 that all general practices should have direct access to a defined minimum set of diagnostic imaging tests for patients with concerning symptoms who do not meet National Institute for Health and Care Excellence criteria for an urgent suspected cancer referral (2–4). The guidance names chest radiography, CT of the chest, CT of the abdomen and pelvis, ultrasound of the abdomen and pelvis, and brain MRI, and sets an expectation that an urgent direct access referral is completed, including the report, within four weeks (4).'),
      p('The policy arrived without dedicated additional workforce or equipment funding, at a time when imaging services were still recovering from the pandemic and when both the radiologist and radiographer workforces were documented as substantially undersized relative to demand (5–7). Whether an access policy of this kind increases activity, and whether any increase translates into faster diagnosis, is therefore an open question with direct implications for imaging departments. We examined both.'),

      h('Methods'),
      p('We used the NHS England Diagnostic Imaging Dataset (DID), which publishes monthly counts of imaging events at provider level, separately identifying events attributable to GP direct referral and reporting median waiting times from request to test (8). The DID reports these for defined indicator groups described as events potentially used for the detection of specific cancers, which map closely onto the modalities the policy names. We analysed the four covered indicator groups — brain MRI, CT chest and abdomen/pelvis, ultrasound abdomen/pelvis, and chest radiography — and retained ultrasound of the kidney and bladder, which the guidance does not name in its minimum set, as a comparator.'),
      p('The analysis covers April 2018 to March 2025 for NHS trusts (organisation codes beginning R), built directly from the published tables rather than from a bespoke extract. We excluded March 2020 to March 2021, when imaging activity collapsed and recovered. This left 160 trusts and 71 months, of which 29 follow the announcement.'),
      p('The identification problem in a simple before-and-after comparison is that diagnostic activity was changing for reasons unrelated to the policy. We therefore used a difference-in-differences design in which each trust supplies its own control: GP direct referrals are the treated series and all other referrals to the same trust, in the same modality and the same month, are the comparator. We estimated the natural logarithm of monthly events on an indicator for the post-announcement period interacted with the GP series, absorbing trust-by-source fixed effects and calendar-time fixed effects, and allowing GP-specific calendar-month effects so that any seasonality particular to general practice is not attributed to the policy. Standard errors are clustered by trust. Waiting times were modelled the same way; because the DID publishes medians for GP referrals and for all referrals but not for non-GP referrals separately, the waiting-time comparator includes GP activity and those estimates are therefore attenuated.'),
      p('We pre-specified three robustness checks: a placebo announcement date within the pre-policy period, a model allowing a differential linear trend between the two series, and adjustment for the community diagnostic centre programme, the main competing explanation for rising diagnostic volume over this period (11). We measured community diagnostic centre exposure as the cumulative number live in a trust’s region, from the government’s operational list, interacted with the GP series. Because treatment timing is common rather than staggered, and the comparator series are never treated, two-way fixed effects estimates the average treatment effect on the treated without the weighting problems that arise under staggered adoption; we nonetheless confirmed the main estimate against the Callaway and Sant’Anna doubly robust estimator (12). Analyses were conducted in Python 3.11 and Stata 18; code and derived data are available at https://github.com/igorfrancetic/gpda.'),

      h('Results'),
      p('GP direct referrals accounted for 25.1% of cancer-detection imaging events in the pre-pandemic period and 26.7% after the announcement (Figure 1).'),
      p('In the difference-in-differences model, GP direct referrals in covered modalities rose by 10.1% relative to other referrals at the same trust (95% CI 5.1 to 15.3, p<0.001), and remained elevated across the 29 post-announcement months. The increase was concentrated in cross-sectional imaging: brain MRI 35.2% (95% CI 24.7 to 46.7) and CT 14.9% (95% CI 6.6 to 23.8), with chest radiography 12.9% (95% CI 8.5 to 17.6) and ultrasound of the abdomen and pelvis 7.1% (95% CI −0.2 to 15.0). Ultrasound of the kidney and bladder, which the guidance does not name, rose by 8.2% and was not statistically distinguishable from zero (95% CI −4.6 to 22.8) (Table 1, Figure 2).'),
      p('No covered modality showed a statistically significant change in median waiting time from request to test. Pooled across the four the change was +3.1% (95% CI −1.8 to 8.3, p=0.22). Brain MRI, the modality with by far the largest activity increase, showed no reduction at all (+3.9%, 95% CI −4.2 to 12.7).'),
      p('A placebo announcement set at November 2021 and estimated on pre-policy data alone produced no effect (−1.1%, 95% CI −6.1 to 4.3, p=0.69). Allowing a differential linear trend between the two series left the activity result intact and larger (16.8%, 95% CI 9.1 to 25.1), the fitted differential pre-trend being small and negative (−0.14% per month), which if anything makes the main estimate conservative. Truncating the series at November 2023 gave 10.7% (95% CI 6.2 to 15.4). Every one of the 79 dated first-wave community diagnostic centres opened between July 2021 and August 2022, entirely before the announcement; adding regional community diagnostic centre exposure left the estimate intact and slightly larger (13.5%, 95% CI 5.7 to 22.0), with the exposure term itself null (−2.2%, p=0.19). The Callaway and Sant’Anna estimator gave a comparable aggregate effect.'),

      h('Discussion'),
      p('Using each trust as its own control, GP direct access referrals for cancer-detection imaging increased by about a tenth relative to other referral sources following the November 2022 announcement, and the increase was largest in exactly the modalities where capacity is most constrained. Yet the waiting times the policy set out to reduce did not fall in any covered modality, and if anything lengthened slightly for GP referrals relative to everyone else.'),
      p('The same pattern has been reported for the other major diagnostic capacity policy of this period. Evaluating the community diagnostic centre programme, Sivey and Wen found that centres raised diagnostic volume by about 6% but had no effect on waiting times, which they read as a demand response to greater availability (11). That two independent policies, evaluated in different datasets with different designs, both raised activity without improving timeliness suggests the constraint is not the referral pathway but the capacity behind it.'),
      p('The most economical reading is that the policy succeeded in changing referral behaviour in primary care but was absorbed by imaging departments that had no additional capacity with which to absorb it. On that reading, the four-week expectation set out in the guidance functioned as an aspiration rather than a constraint, and the additional demand was accommodated by lengthening the queue rather than by shortening it. The pattern is consistent with the workforce shortfalls documented by the Royal College of Radiologists and the Society of Radiographers (6,7), and with earlier evidence that referral responses to diagnostic waiting times depend on whether receiving providers can accommodate additional volume (9,10).'),
      p('For imaging services the practical implication is that access policies and capacity policies are not substitutes. An instruction to open a pathway changes what arrives at the department; it does not change what the department can deliver. Where a direct access pathway is introduced without matched capacity, the measurable result is more examinations at the same or slightly slower speed, and the burden falls on modalities such as MRI where reporting capacity is scarcest.'),
      runs([{ t: 'Limitations. ', b: true }, { t: 'This is an observational study of aggregate provider returns and cannot attribute causality with certainty. The control series is other referrals to the same trust, which would be a poor control if the policy itself displaced non-GP activity; such displacement would bias our activity estimate upwards and our waiting-time estimate towards no effect, so the direction of any such bias reinforces rather than weakens the waiting-time conclusion. The DID indicator groups approximate but do not exactly reproduce the tests named in the guidance. Waiting-time comparators include GP activity, attenuating those estimates. A small differential pre-trend was present, although adjusting for it did not weaken the findings. The community diagnostic centre programme continued to expand after 2022, and while the first wave opened entirely before the announcement and adjustment for regional exposure did not change our estimates, later waves may contribute to activity growth in the final years of the series. Finally, we cannot observe whether the additional imaging yielded additional cancer diagnoses, which is the outcome that ultimately matters.' }]),

      h('Declarations', 24),
      p('Funding: Igor Francetic was supported by the National Institute for Health and Care Research, School for Primary Care Research (grant nr. 610). The funder had no role in the study.', { size: 20, after: 70 }),
      p('Competing interests: None declared.', { size: 20, after: 70 }),
      p('Ethics approval: Not required. The study uses aggregate, publicly available provider-level statistics containing no patient-identifiable information.', { size: 20, after: 70 }),
      p('Data availability: The Diagnostic Imaging Dataset is published by NHS England. Derived data and all analysis code are available at https://github.com/igorfrancetic/gpda.', { size: 20, after: 70 }),
      p('Reporting: This study follows the STROBE reporting guideline for observational studies; a completed checklist is provided as supplementary material.', { size: 20, after: 200 }),

      new Paragraph({ children: [new PageBreak()] }),
      h('Table 1'),
      p('Table 1: Adjusted change in GP direct referral imaging activity and median waiting time after the November 2022 announcement, relative to all other referrals at the same trust', { bold: true, size: 20, after: 100 }),
      t1,
      p('Difference-in-differences estimates from log-linear models with trust-by-source and calendar-time fixed effects and GP-specific calendar-month effects; standard errors clustered by 160 trusts. Period April 2018 to March 2025, excluding March 2020 to March 2021. Waiting-time comparators include GP activity and are therefore attenuated.', { italics: true, size: 17, after: 260 }),

      h('Figures'),
      p('Figure 1: GP direct referrals as a percentage of all cancer-detection imaging events, English NHS trusts, April 2018 to March 2025', { bold: true, size: 20, after: 60 }),
      img('BJR_Fig1.png', 560, 256),
      p('Horizontal bars show period means. The shaded band marks the pandemic disruption excluded from the models.', { italics: true, size: 17, after: 200 }),
      p('Figure 2: Adjusted change in GP direct referral activity and median request-to-test waiting time, by modality', { bold: true, size: 20, after: 60 }),
      img('BJR_Fig2.png', 560, 226),
      p('Points are difference-in-differences estimates with 95% confidence intervals, relative to all other referrals at the same trust. Coloured intervals exclude zero. Ultrasound of the kidney and bladder is not named in the guidance and is shown as a comparator.', { italics: true, size: 17, after: 260 }),

      new Paragraph({ children: [new PageBreak()] }),
      h('References'),
      ref(1, 'National Health Service. The NHS Long Term Plan. London: NHS; 2019. Available from: https://www.longtermplan.nhs.uk/publication/nhs-long-term-plan/'),
      ref(2, 'Merriel SWD, Francetic I, Buttle P. Direct access to imaging for cancer from primary care. BMJ. 2023 Feb 9;380:e074766.'),
      ref(3, 'NHS England. NHS gives GP teams direct access to tests to speed up cancer diagnosis. 2022. Available from: https://www.england.nhs.uk/2022/11/nhs-gives-gp-teams-direct-access-to-tests-to-speed-up-cancer-diagnosis/'),
      ref(4, 'NHS England. Urgent GP direct access to diagnostic services for people with symptoms not meeting the threshold for an urgent suspected cancer referral. 2023. Available from: https://www.england.nhs.uk/long-read/urgent-gp-direct-access-to-diagnostic-services-for-people-with-symptoms-not-meeting-the-threshold-for-an-urgent-suspected-cancer-referral/'),
      ref(5, 'NHS Improvement, NHS England. Transforming imaging services in England: a national strategy for imaging networks. 2019. Report No.: CG 51/19.'),
      ref(6, 'The Royal College of Radiologists. Clinical Radiology Workforce Census 2023. London: The Royal College of Radiologists; 2023.'),
      ref(7, 'College of Radiographers. Diagnostic radiography workforce UK census. London: Society of Radiographers; 2022.'),
      ref(8, 'NHS England. Diagnostic Imaging Dataset. Available from: https://www.england.nhs.uk/statistics/statistical-work-areas/diagnostic-imaging-dataset/'),
      ref(9, 'Hayes H, Meacock R, Stokes J, Sutton M. How do family doctors respond to reduced waiting times for cancer diagnosis in secondary care? Eur J Health Econ. 2024;25(5):813–28.'),
      ref(10, 'Hayes H, Meacock R, Stokes J, Sutton M. The effect of local hospital waiting times on GP referrals for suspected cancer. PLOS ONE. 2024;19(5):e0294061.'),
      ref(11, 'Sivey P, Wen J. The effect of community diagnostic centres on volume and waiting time for diagnostic procedures in the UK. Health Policy. 2024;147:105101.'),
      ref(12, 'Callaway B, Sant’Anna PHC. Difference-in-differences with multiple time periods. J Econom. 2021;225(2):200–30.')
    ]
  }]
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync('BJR_manuscript.docx', b); console.log('written', b.length); });
