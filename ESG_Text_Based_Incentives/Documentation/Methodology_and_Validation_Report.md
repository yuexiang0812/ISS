# Text-Based ESG Executive Incentives from ISS Incentive Lab (1998–2021)
## Measurement Methodology and Validation Report — classifier v1.0

> **Status: PROVISIONAL.** Every label is produced by the frozen deterministic classifier v1.0. No independent human reference labels exist yet, so **no accuracy statistic is reported**. A blind validation sample (601 units), a coding guideline and the scoring code are ready (§12).

### 中文摘要
- **范围与方法**：本项目对 ISS Incentive Lab 1998–2021 年全部 814,091 条业绩目标记录，用同一套文本规则（v1.0，50 条规则）做 ESG 分类，产出 KPI、Grant、高管、CEO、非 CEO 和公司-年层面的数据集。每个标签都是 1 / 0 / 未知三态。
  - ISS 原有的 ESG 分类（metricType 与 2018 年新增的 metric 标签）只用于诊断对比，从不作为分类依据。
- **2018 年断点是分类造成的**：ISS 原分类显示的 2018 年跳升，在统一文本分类下不存在。业绩型 grant 的公司-年 Strict ESG 采用率下界在 2017 年为 14.6%，2018 年为 15.5%。
- **真正的上升在 2020–2021 年**：2021 年采用率下界为 30.4%。增长主要来自采用面扩大（广延边际），社会类（S）是主要驱动。
- **未知比例需要如实报告**：大量年度奖金指标（如 "Individual Performance"）无法判断，所以采用率给出下界、完整样本和上界三种口径。
- **验证尚未完成**：没有人工标注之前，所有标签均为暂定（Provisional）。

---

## 1. Raw ISS data inventory
- **Location**: the 18 Stata files under `01. Incentive Lab/` plus the ISS User Guide (8 July 2021).
- **Inventory output**: `Documentation/data_inventory_files.csv` lists rows, columns, candidate-key duplicate counts and year range; `data_inventory_fields.csv` lists every field with its dtype, non-missing count, number of `-9999` missing codes and blanks. Log: `Logs/01_data_inventory.log`.

Files used:

| File | Role | Rows |
|---|---|---|
| 08 Grants of Plan-Based Awards (GpbaGrant) | grants, award attributes, performance type | 469,573 (469,429 distinct grantID) |
| 02 Absolute Performance Goals (GpbaAbs) | goal text and payout | 716,130 |
| 16 Relative Performance Goals (GpbaRel) | goal text and peer benchmark | 89,985 |
| 03 Accelerated Performance Goals (GpbaAcc) | acceleration conditions | 7,976 |
| 12 Participant Data by FY | identity, title, role codes, currentCEO | 474,170 |
| 05 Company Data by FY | firm-year universe, name, ticker, CUSIP | 33,328 |

The other files (ownership, director compensation, peers, holding requirements, consultants, outstanding equity, exercises) are not needed for the construct.
- The Summary Compensation Table (file 18) has **no participantID column** in this delivery, although the guide lists one. It therefore cannot be linked to executives and is not used.

## 2. Source files and field definitions
Field meanings follow the ISS User Guide (fields listed in `data_inventory_fields.csv`). Key conventions verified in the data:
- **Missing codes.** Numeric missing values are coded `-9999.xx`, and `-99999` also occurs. They are converted to missing: 25,159 `grantDateFV` and 22,968 `nonEquityTarget` values. Date missing values are coded `01/01/9999`; 117,906 grant dates are converted to missing. One negative `grantDateFV` and 18 negative `vestHighGrant` values are impossible and are set to missing.
- **Fiscal year.** Defined by ISS's 10-July rule. Goal-record `fiscalYear` equals the grant's `FiscalYear` in 100% of matched records.
- **`metricType`.** Before 2018 it takes Accounting / Other / Stock Price. From 2018 it is granular and adds Social / Environment / CSR. Per the guide, "Market-related" is the old "Stock Price".
- **`metric`.** The ESG labels (Staff Health And Safety, Diversity, Csr, Climate Change And Energy Use, …) first appear in 2016–2018. Only **58 of 10,603** rows carrying them are dated before 2018. They are therefore part of the 2018 re-taxonomy (`Logs/03_goal_extraction.log`).
- **`metricOther`.** This is the descriptive text. It is blank for **68% of goal records in 1998** and about **50% in 2010**, but for **3% in 2018 and 0% from 2020**. This is a text-availability break and it is reported, not imputed.

## 3. Entity and identifier relationships
```
CompanyFY (CIK, fiscalYear) 1───* GpbaGrant (grantID; CIK, FY, FM, participantID)
ParticipantFY (CIK, FY, FM, participantID) 1───* GpbaGrant
GpbaGrant 1───* GpbaAbs / GpbaRel / GpbaAcc  (grantId, goal id, periodID)
```
- **Goal ids are recycled across grants.** `absId` alone has 191,919 duplicates and `(absId, periodID)` has 54,978. The true record key is **(goal_source, grantId, goal_id, periodId)**, which has 0 duplicates in all three goal files.
- **grantID.** 144 grantIDs appear twice (285 rows). The duplicate rows agree on CIK, participant, year, month and award type, so they are de-duplicated safely.
- **Goal-to-grant linkage.** 99.9988% of goal records match a grant. Ten records belonging to three grantIDs are absent from the grants table; they are listed in `Data/Intermediate/audit_goal_grants_missing_in_grant_table.csv`.
- **ParticipantFY key.** The table is unique on (CIK, FY, FM, participantID). It is *not* unique on (CIK, FY, participantID): there are 1,007 duplicates caused by fiscal-month changes. Grants are therefore matched on all four fields; 99.975% match (117 unmatched grants are listed in an audit file).
- **CompanyFY** is unique on (CIK, FY). 776 firm-years have no grants. Every grant firm-year exists in CompanyFY.

## 4. Definition of distinct performance KPIs
- **Raw goal record** = objective × measurement period (814,091). This level is kept in `ESG_Goal_Record_Classification.dta`.
- **KPI** = **(grantid, goal_source, text_id)**, giving 654,123 KPIs.
  - It collapses the measurement periods of the same objective (84,463 KPIs span more than one period).
  - It collapses repeated objectives with identical text in the same grant, e.g. A1 = year-1 EPS and A2 = year-2 EPS (4,849 KPIs, `kpi_duplicate_flag = 1`).
  - Absolute, relative and accelerated versions of a metric remain separate KPIs, because they are different contractual conditions.
- **No collapsing across grants or executives at KPI level.** Each executive's grant is a separate award.
- **Distinct-KPI shares at aggregate levels.** At executive, CEO and firm level, a distinct KPI is (goal_source, text_id) *within the unit*. The same metric used in the plans of five NEOs therefore counts once in the firm-year KPI share.
- **Reconciliation:** Σ `kpi_source_count` = 814,091 = number of goal records.

## 5. Grant and executive matching methodology
- Grants carry CIK, fiscal year, fiscal month and participantID directly, so no cross-year or name-based matching is used.
- An executive-firm-year is (CIK, FY, participantID). Identity is attached by an exact 4-field match to ParticipantFY. `exec_identity_match_status` records matched_exact / partially_matched / unmatched; 117 grants are unmatched.
- **Performance-based grant** = `performancetype` ∈ {Abs, Rel, AbsRel}; time-based = Time.
  - Hybrid absolute+relative awards are flagged (`grant_is_hybrid_absrel`).
  - Time grants with acceleration conditions (4,496 with goals, 171 declared without goal data) are flagged `grant_time_with_acceleration`. They are excluded from the performance-grant denominator, but their ACC KPIs still count as performance conditions for grant-level ESG linkage.
- **Goal availability** (`grant_goal_status`):

| Status | Grants |
|---|---|
| perf_with_goals | 233,384 |
| perf_goals_missing (missing data ≠ no condition) | 159 |
| time_no_perf_condition (reliably no ESG condition) | 231,168 |
| time_with_accel_goals | 4,496 |
| time_accel_declared_goals_missing | 171 |
| type_missing | 51 |

## 6. CEO identification methodology
CEO status is read from ParticipantFY `currentCEO` (True/False), with role codes (`CEO`; `UC` = segment CEO is never treated as company CEO; `FO`/`R` = former/retired) as a fallback. The status of each firm-year is assigned as follows:

| Status | Firm-years | Treatment |
|---|---|---|
| unique_current_ceo_flag | 32,231 | strict CEO sample (`ceo_strict_sample = 1`) |
| multiple_current_ceo_flags | 505 | all candidates kept; none silently selected; in exception table |
| rolecode_fallback_unique | 14 | kept as an alternative (not strict) |
| rolecode_ambiguous | 1 | exception table only |
| no_ceo_identified | 515 | exception table only |

The exception table is `Data/Intermediate/audit_ceo_exceptions.csv` (1,960 rows, 1,035 firm-years).
- **Non-CEO** executives are those with `currentCEO` = 0 explicitly, in a firm-year with an identified CEO, who are not a CEO candidate: 130,794 executive-years.
- 3,219 executive-years with unknown role are **excluded** from non-CEO aggregates and counted in `nonceo_n_role_unknown_execs`.

## 7. Text normalization
Applied to `metricOther`:
- NFKC normalisation
- Typographic quotes and dashes, and the source mojibake `‚Äô`, are normalised
- Whitespace is collapsed
- Trailing punctuation is stripped
- The result is lower-cased for the key

**Classification unit** = `metric || lower(metricOther)`, plus `|| ctx=` only when the text is blank (§11). This gives 38,590 units. Identical text receives the identical label in every year.

## 8. ESG construct definition
An **ESG-linked performance condition** is a performance condition whose text explicitly references an environmental, social or governance objective. The construct is about the condition itself, not about whether the firm is ESG-oriented.
- **Strict ESG**: clearly identifiable E, S or G content (§10).
- **Extended ESG** = Strict ESG plus explicitly stakeholder-oriented conditions: customers, product/patient safety and quality, healthcare quality, privacy and fair treatment, customer-facing service reliability, and community engagement.
  - The invariant Strict = 1 ⇒ Extended = 1 holds (asserted in code).
  - `esg_extended_only` identifies the additions.

## 9. Strict and Extended classification methodology
**Approach.** A deterministic, versioned rule engine (`Code/esg_rules.py`, `Code/classify.py`) with **50 regex rules**, exported with rationale to `Dictionaries/b_revised_rules_v1.0.csv`. Rules run in priority order and each match *consumes* its text span:
1. Masks for false-positive phrases. Some masks also count as non-ESG evidence, e.g. "safety and soundness" or "economic environment".
2. Routed specific phrases, e.g. "product safety" → Extended, before generic "safety".
3. Strict ESG rules, starting with multi-pillar ESG phrases, then E, S and G.
4. Extended (stakeholder) rules.
5. Ambiguous rules.
6. ESG-adjacent exclusions.
7. Non-specific placeholders.
8. Non-ESG financial/operating evidence.
9. Filler words.

**Decision.** Strict = 1 if any Strict rule fires. Strict is Unknown if an ambiguous or placeholder rule fires, or if nothing fires. Strict = 0 only with **positive** non-ESG, adjacent or stakeholder evidence: failing to find an ESG keyword is never sufficient for 0. Extended follows analogously.

**`metric` × `metricOther` joint reading.** Before 2018, `metricOther` often holds only a qualifier (`metric` = Cashflow, `metricOther` = Free). The two fields are therefore read together:
- Financial standardised labels (EPS, Sales, …; available 1998–2021) count as non-ESG evidence.
- "Customer Satisfaction" counts as Extended evidence.
- Placeholder labels (Other, Individual, Vague, Operational, Non-Financial, Business Unit, Discretionary) carry no evidence.
- **2018-taxonomy ESG labels and ISS ESG metricTypes are never used.**

**Starting point: AGHJ (2025).** The 953 terms are reproduced verbatim (`a_paper_dictionary_AGHJ2025_953.csv`, with page numbers). Only 3 of the 81 removed terms are disclosed in A.4 (complaint, cyber, trust); the other 78 are **not reconstructed**. Every one of the 953 terms was reviewed against the 1998–2021 texts (`b_paper_keyword_review_v1.0.csv`):

| Decision | Keywords |
|---|---|
| retained Strict (≥90% of their matches remain Strict) | 128 |
| retained with context exclusions | 10 |
| keyword alone insufficient → context required (mostly Strict / mostly non-ESG / mixed in context) | 74 / 84 / 73 |
| reassigned to Extended-only | 11 |
| excluded as ESG-adjacent by definition | 18 |
| excluded generic / false positive | 4 |
| no occurrence in ISS 1998–2021 (112 covered by a v1 rule; 439 not carried forward/untested) | 551 |

New expressions not matched by any AGHJ term are listed in `b_new_expressions_v1.0.csv`. Examples: EH&S, HS&E, days-away-restricted variants, D&I / DE&I, "ethical conduct", flaring, reportable/off-property releases, scrubbers, reclamation, gas-leak backlogs, corporate well-being, staff/teller turnover. The change log is `Dictionaries/c_change_log.csv`.

**No trend calibration.** No rule references years, ISS categories or trend targets. Rule development used frequency-ranked and random reviews of all years jointly.

## 10. E, S and G coding rules (summary; exact regex in `b_revised_rules_v1.0.csv`)
**Environmental (E):**
- GHG, carbon, CO2, methane, SF6, NOx, SO2, flaring, LDAR, scope 1–3, net zero, scrubbers
- Climate change, action, risk or policy; TCFD
- Renewable energy *adoption*, carbon-free capacity share, electrification, energy-use/intensity reduction
- Water use and quality, wastewater
- Waste, recycling, plastics, landfill
- Spills and environmental releases
- The word "environmental" (business senses of "environment" are masked); biodiversity, reclamation, pollution

**Social (S):**
- Occupational, process and public safety (safety, TRIR, DART, OSHA, lost time, fatalities, SIF, vehicle accidents, near misses, HSE/EHS/EH&S, process safety, gas leaks/damage prevention, wildfire mitigation, NRC findings)
- DEI, including supplier diversity
- Specific human capital: engagement/satisfaction surveys, voluntary or employee turnover, retention of talent, training programmes, wellbeing, mental health, human capital
- Community investment, volunteering, philanthropy
- Defined social-access goals: affordable-housing goals, duty to serve, financial inclusion
- Human rights and labour standards

**Governance (G):** ethics, code of conduct, anti-corruption/bribery, FCPA, whistle-blowing, corporate governance, board composition/diversity/evaluation, say-on-pay.

**General (multi-pillar):**
- ESG, CSR, corporate citizenship and ESG ratings (DJSI, GRESB, Sustainalytics, CDP, GRI): Strict = 1, with E/S/G **unknown** unless a pillar term co-occurs.
- "Sustainability" is treated as a qualifier when it accompanies a pillar term, e.g. "Environmental Sustainability" → E only.

## 11. Treatment of ambiguous and generic metrics
- **Placeholders** (Individual Performance, Strategic Objectives, Corporate Goals, Discretionary, Non-Financial, Other, Leadership, Operational Goals, Scorecard) → Unknown. They remain Unknown even when a financial term co-occurs, e.g. "EPS and Individual Performance".
- **Ambiguous** terms → Strict Unknown:
  - Energy efficiency / DSM (an environmental vs operating-cost objective)
  - Bare "water", "waste", "green", "clean", "renewables"
  - Notices of violation without environmental context
  - Bare "integrity", "social", "turnover", "attrition"
- **ESG-adjacent but excluded by definition** (0 / 0, flagged in `adjacent_flags`):
  - Generic compliance, regulatory exams, risk management, internal controls, SOX, audit, cybersecurity, AML/BSA
  - Generic talent, succession, leadership development, culture, HR, hiring, teamwork
  - Renewable-energy business-line execution (wind/solar projects, renewable portfolio growth)
- **Blank text** (`metric` and `metricOther` both blank/placeholder; 60,986 goal rows, overwhelmingly pre-2018 relative TSR/stock-price goals):
  - The *time-consistent* financial metricType (Accounting; Stock Price = Market-related) is admitted as **structured context** → 0, with `classification_method = structured_context` and confidence medium.
  - The text-only label is kept separately as Unknown (`esg_strict_textonly`).
  - Other blank units → Unknown (`no_text`). Blank units with a 2018 ESG label → Unknown (`iss_esg_label_only`).
- **Mixed texts** ("EPS and Safety") → Strict = 1, flagged `mixed_esg_and_financial_text`. Seven units with an ESG term under a financial `metric` label are flagged `esg_term_under_financial_label` for review.

## 12. Classification verification results
**Development (completed).** Rules were developed on all years jointly by:
- reviewing the 402 AGHJ keywords that occur in the data, with their most frequent and their non-ISS matches;
- reviewing the top Unknown, Strict = 1, Extended-only and ambiguous units by frequency;
- reviewing a random sample of 150 low-frequency Strict = 1 units;
- reviewing a random sample of 300 Strict = 0 units;
- reviewing all paper-versus-revised disagreements.

Each error found led to a rule change, documented in `c_change_log.csv`. Examples: "inclusive of dividends", TV-audience "women viewers", "scrubber securitization", "NOV" (National Oilwell Varco), "Retain key talent".

**Independent validation (pending human labels).**
- **Rules frozen.** Rules MD5 = `9cf1cf0d751f3822425d87253f33addb`.
- **Sample.** 601 units drawn with seed 20261031 across 32 strata: period of use (pre-2018 only / post-2018 only / both) × predicted class (Strict / Extended-only / non-ESG / Unknown) × frequency (1 / 2–9 / 10+ rows).
- **No repeated descriptions.** Each unit is sampled once, so repeated occurrences of the same description are not double counted.
- **Weights.** Unit weights N_h/n_h, and row weights N_h/n_h × n_goal_rows.
- **Materials.** Blind coding sheets for two coders, the answer key and guidelines (`Validation/CODING_GUIDELINES.md`).
- **Scoring (Step 13).** Computes precision, recall, F1, FPR, FNR and Unknown rate by period, dimension and frequency; stratum-weighted, with 500-draw bootstrap CIs over units; and Cohen's kappa.
- **Until labels exist,** `Validation/validation_status_v1.0.json` = `pending_human_labels`, and **no accuracy figure is claimed.**

**Comparison with AGHJ (2025)** (`Validation/e_*.csv`; goal-record level, 1998–2021):

| | v1 Strict = 1 | v1 Strict = 0 | v1 Unknown |
|---|---|---|---|
| AGHJ = 1 (53,123 rows) | 29,331 | 16,617 | 7,175 |
| AGHJ = 0 (760,968 rows) | 575 | 648,557 | 111,836 |

The 23,792 AGHJ-positive goal rows that v1 does **not** classify as Strict ESG (16,617 set to 0, 7,175 Unknown) fall into these mutually exclusive unit categories:

| Category | Units | Goal rows |
|---|---|---|
| Extended-only (customer retention, SAIDI, patient satisfaction …) | 381 | 3,082 |
| ESG-adjacent by definition (regulatory compliance, succession, culture …) | 907 | 5,290 |
| Unknown, no adjacent flag (e.g. "Leadership", "Integrity", "Energy efficiency") | 1,160 | 6,992 |
| Generic or false positive (cost/debt "reduction", "policies in force", loan-covenant "violations", company names) | 1,484 | 8,428 |

In the other direction, v1 identifies 88 units (575 rows) as Strict ESG that no AGHJ term matches (`b_new_expressions_v1.0.csv`). The AGHJ method also has no Unknown state: blank `metricOther` (up to 68% of rows in early years) is silently treated as non-ESG.

## 13. Missingness and coverage
Goal-record level (`Annual_Analysis/annual_text_coverage.csv`):

| Year | metricOther blank | v1 Strict Unknown share |
|---|---|---|
| 1998 | 68% | 21% |
| 2008 | 55% | 14% |
| 2017 | 34% | 13% |
| 2021 | 0% | 13% |

Despite the very different blank-text rates, Unknown shares are similar across years: blank financial-label rows are informative, and structured context is used.

At unit level, adoption Unknown is large because one unresolved KPI in any performance grant leaves a non-adopting unit Unknown. Annual bonus plans often contain "Individual performance". Hence every share is published with `_lb` / `_ub` and coverage, and adoption is reported as lower bound / complete-case / upper bound.

## 14. Exact numerator / denominator definitions
Full details are in `Documentation/variable_dictionary.csv`, which gives the formula, numerator, denominator, values, missing interpretation and source for all 459 variables.

**Grant ESG**
- 1 = ≥1 KPI is ESG.
- 0 = all KPIs are 0, or the grant is a time grant with no performance condition.
- `.` otherwise (including performance grants with missing goal data).

**Adoption (unit)**
- 1 = ≥1 grant in the universe is 1.
- 0 = all grants are 0.
- `.` otherwise, or empty universe.
- Universes: ALL grants / PERF grants.

**Grant share**
- = #ESG grants / #grants in universe, published only if #unknown = 0.
- `_lb` = #ESG / N; `_ub` = (#ESG + #unknown) / N; coverage = #known / N.

**KPI share**
- = #distinct ESG KPIs / #distinct KPIs, with the same exact / lb / ub rule.

**E/S/G grant share**
- = #performance grants with a confirmed E (S, G) condition / #performance grants. This is a lower bound when general ESG terms leave the pillar unresolved.

**Value share**
- = Σ grant-date fair value of grants containing ≥1 Strict ESG condition / Σ fair value of grants with reported value.
- **This is not value attributable to ESG.** ISS `percentVest` is the share of the award per *measurement period* and interacts with AND/OR performance groupings and "extra" adjustments (User Guide pp. 4–6). Reliable KPI weights are therefore not observable and none are fabricated.

## 15. Dataset observation counts and 16. Primary keys
Also in `Documentation/dataset_summary.csv`; every key was verified unique and non-missing on re-read.

| Dataset | Obs | Vars | Primary key | Years |
|---|---|---|---|---|
| A `ESG_Text_Dictionary.dta` | 38,590 | 43 | text_id | 1998–2021 |
| B `ESG_KPI_Master.dta` | 654,123 | 36 | kpi_id (= grantid + goal_source + text_id) | 1998–2021 |
| (B-alt) `ESG_Goal_Record_Classification.dta` | 814,091 | 29 | goal_record_id | 1998–2021 |
| C `ESG_Grant_Master.dta` | 469,429 | 69 | grantid | 1998–2021 |
| D `ESG_Executive_Firm_Year.dta` | 164,832 | 73 | cik + fiscalyear + participantid | 1998–2021 |
| E `ESG_CEO_Firm_Year.dta` | 33,278 (strict sample 32,231) | 76 | cik + fiscalyear + participantid | 1998–2021 |
| F `ESG_Firm_Year_Master.dta` | 33,328 | 70 | cik + fiscalyear | 1998–2021 |
| G `ESG_NonCEO_Firm_Year.dta` | 31,944 | 63 | cik + fiscalyear | 1998–2021 |

**Stata names.** Names are ≤ 32 characters. Overlong preferred names are shortened by a fixed rule (`_extended` → `_ext`, `compensation` → `comp`, `classification` → `class`, `_strict` → `_str`); the mapping is in the variable dictionary (`preferred_name`).

## 17. Matching and reconciliation statistics
| Check | Result |
|---|---|
| Goal records → grant | 99.9988% matched (10 records, 3 grants unmatched) |
| Grants → ParticipantFY (exact 4 keys) | 99.975% matched (117 unmatched) |
| Grants → CompanyFY firm-year | 100% |
| Σ KPI source rows = goal records | 814,091 = 814,091 |
| Σ grant KPIs = KPI master (matched grants) | equal |
| esg + non-esg + unknown KPIs = n_kpis (each grant) | holds |
| Σ exec grants = Σ firm grants = grant master | 469,429 |
| Firm ESG / perf / all grant counts = Σ over executive-years | equal for every firm-year |
| All shares and coverages in [0, 1]; lb ≤ ub; adoption consistent with share | all pass |
| Strict = 1 ⇒ Extended = 1 | 0 violations |

All of these are asserted in code; any failure stops the pipeline.

## 18. Annual ESG trends
Full tables: `Annual_Analysis/annual_firm_year.csv`, `annual_executive_year.csv`, `annual_ceo_year_strict_sample.csv`.

Firm-years with performance grants, Strict ESG adoption:

| FY | Firms | Adopt lb | Complete-case | Adopt ub | Extended lb | Mean perf-grant share lb | Mean perf coverage | ISS ESG (diag) |
|---|---|---|---|---|---|---|---|---|
| 1998 | 689 | 3.2% | 6.0% | 49.8% | 6.1% | 1.8% | 0.61 | 0 |
| 2008 | 1,236 | 10.7% | 21.1% | 60.0% | 15.0% | 5.4% | 0.67 | 0 |
| 2015 | 1,263 | 14.6% | 34.1% | 71.7% | 18.9% | 7.1% | 0.67 | 0 |
| 2016 | 1,200 | 14.1% | 32.0% | 70.1% | 18.3% | 6.5% | 0.69 | 0.1% |
| 2017 | 1,188 | 14.6% | 29.1% | 64.6% | 19.2% | 6.7% | 0.73 | 0.3% |
| 2018 | 1,160 | 15.5% | 30.8% | 65.1% | 20.3% | 7.5% | 0.74 | 13.7% |
| 2019 | 1,128 | 16.8% | 32.1% | 64.4% | 21.6% | 7.9% | 0.75 | 16.8% |
| 2020 | 1,090 | 19.6% | 37.3% | 67.0% | 24.7% | 9.5% | 0.75 | 19.3% |
| 2021 | 956 | 30.4% | 52.8% | 72.8% | 34.9% | 14.2% | 0.77 | 30.1% |

Firm-level pillar adoption (lb), 2017 → 2018 → 2021:

| Pillar | 2017 | 2018 | 2021 |
|---|---|---|---|
| E | 4.5% | 5.5% | 9.4% |
| S | 13.8% | 14.7% | 25.0% |
| G | 0.8% | 0.7% | 1.4% |

Executive level, Strict adoption lb (CEO strict sample in parentheses):

| Year | Executives (CEO) |
|---|---|
| 2017 | 13.6% (13.3%) |
| 2018 | 14.8% (14.7%) |
| 2021 | 29.4% (29.7%) |

## 19. Interpretation of the 2018 classification change
1. **The rise survives uniform text classification, but the 2018 jump does not.**
   - ISS's own ESG categories move from 0.3% (2017) to 13.7% (2018) of firm-years.
   - Uniform text classification moves only from 14.6% to 15.5%.
   - At KPI level, text-Strict ESG KPIs number 1,618 in 2017 and 1,641 in 2018 (`break_iss_vs_text_kpi_2014_2021.csv`).
   - The real increase is concentrated in 2020–2021: 19.6% → 30.4%.
2. **The ISS re-classification created an artificial break.**
   - Before 2018, about 1,500–1,700 text-ESG KPIs a year are labelled non-ESG by ISS.
   - From 2018, 80% of ISS-ESG KPIs are text-Strict. The rest are mostly Extended-only (customer and product responsibility, "staff relations" generic workforce) or Unknown.
   - Conversely, 237–426 text-Strict KPIs a year remain ISS non-ESG after 2018, e.g. "Environmental and Safety".
3. **Sample composition is not the explanation.**
   - 1,134 firms are continuing from 2017 to 2018; their adoption goes from 14.0% to 15.3%.
   - 54 firms exit and 26 enter, and both groups have higher adoption (26% / 23%), so composition does not explain a jump.
   - A 2015–2021 balanced panel of firms with known adoption every year (205 firms; positively selected, adoption about 40%) is flat through 2020 and rises in 2021.
4. **Extensive vs intensive margin** (mean firm perf-grant ESG share, lb; Shapley-type split):

| Period | Δ mean share | Extensive | Intensive |
|---|---|---|---|
| 2017–2018 | +0.79 pp | +0.45 | +0.33 |
| 2018–2021 | +6.71 pp | +7.10 | −0.39 |

   The increase is driven by **adoption (extensive margin)**, not by higher intensity among adopters.
5. **Pillars.** Social conditions, mainly safety and DEI, drive the level and the 2020–21 increase. Environmental conditions double from 2018 to 2021. Governance conditions remain rare (about 1%).
6. **Coverage.** Classification coverage of performance grants rises gently from about 0.6 (1998) to 0.77 (2021); there is no discontinuity at 2018.
   - The pre-2018 text-availability problem (blank `metricOther`) mainly affects financial-label rows, which remain classifiable from the time-consistent `metric` label.
   - Bounds therefore remain wide in all years: the gap between lb and ub is about 45–55 pp.

These are descriptive measurement results, not causal effects.

## 20. Limitations and recommended research uses
- **Provisional labels.** No human-validated accuracy exists yet; use the validation package (§12). The human review queue (1,039 flagged frequent units) can resolve many Unknowns in v1.1. Re-running Step 06 onward then propagates confirmed labels and records `human_reviewed`.
- **Wide Unknown band.** It comes from non-specific annual-bonus metrics. Use `_lb` / `_ub` and coverage, report complete-case estimates as a robustness check, or condition on `*_esg_measurement_complete = 1`. Never treat `.` as 0.
- **Definitional choices** (documented, and switchable via flags):
  - Generic compliance/risk/cyber and generic talent/succession are excluded (`adjacent_flags`).
  - Customer service reliability is Extended-only.
  - Renewable business-line execution is excluded.
  - Researchers preferring other boundaries can re-define using `esg_topics` / `adjacent_flags` in Dataset A.
- **No ESG-attributable value.** The value-share measures are exposure measures, i.e. the value of grants *containing* ESG conditions.
- **CEO identification.** Relies on ISS `currentCEO`. Co-CEO and succession years are kept in the exception table, not resolved.
- **Software.** Datasets are built in Python (pandas) and written as labelled Stata 118 `.dta` files (accepted by the user). Stata `.do` versions were not produced because Stata is not available in the build environment.
- **Licensing.** ISS data and any file containing ISS text (`Data/`, `*_local.csv`) are git-ignored and must not be redistributed.

**Recommended primary variables (firm-year):**
- `firm_perf_esg_adopt_strict`
- `firm_esg_perf_share_lb` / `_ub` (with `firm_perf_class_coverage`)
- `firm_esg_kpi_share_lb` / `_ub`
- `firm_esg_[e|s|g]_adopt`
- the Extended counterparts as a robustness check
