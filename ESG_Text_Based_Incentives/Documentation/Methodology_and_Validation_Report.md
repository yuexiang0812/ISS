# Text-Based ESG Executive Incentives from ISS Incentive Lab (1998–2021)
## Measurement Methodology and Validation Report — classifier v1.1

> **Generated file — do not edit by hand.** `Code/18_build_reports.py` rebuilds this report from the current pipeline outputs on every run. The narrative lives in `Code/docgen/methodology_template.md`; every number is read from the outputs named in each section. Generated 2026-10-31 20:55 (git badbbbd).

> **Status: PROVISIONAL.** Every label comes from the deterministic classifier v1.1. No adjudicated human reference labels exist yet, so **no accuracy statistic is reported**. The blind validation sample (601 units, frozen under v1.0), the coding guideline and the scoring code are ready (§12).

> Narrative checks: all 10 interpretive statements in this report are supported by the current outputs.

### 中文摘要
- **范围与方法**：对 ISS Incentive Lab 1998–2021 年全部 814,091 条业绩目标记录，用同一套文本规则（v1.1，57 条规则）做 ESG 分类，产出 KPI、Grant、高管、CEO、非 CEO 和公司-年层面的数据集。
  - 每个标签都是 1 / 0 / 未知三态：只有找到明确的非 ESG 证据才记 0，找不到 ESG 关键词本身不等于 0。
  - ISS 自带的 ESG 分类（metricType 与 2018 年新增的 metric 标签）只用于诊断对比，从不作为分类依据。
- **2018 年的跳升来自 ISS 改分类**：按 ISS 原分类，含 ESG 条件的公司-年比例从 2017 年的 0.3% 跳到 2018 年的 13.7%。按统一文本分类，业绩型 grant 的公司-年 Strict ESG 采用率下界只从 14.6% 变为 15.4%。
- **真正的上升在 2020–2021 年**：采用率下界 2020 年为 19.4%，2021 年为 30.4%。增长主要来自新采用的公司（广延边际），社会类（S）条件占主体。
- **未知比例如实报告**：许多年度奖金指标（如 "Individual Performance"）无法判断是否属于 ESG。因此每个比例都给出下界 lb（未知按 0）、完整样本 cc 和上界 ub（未知按 1）。
- **验证状态**：尚未完成。在人工标注返回之前，所有标签都是暂定（Provisional），不报告任何准确率。601 个单元的盲编码样本、编码手册与评分程序均已就绪。
- **本版本修改**：v1.1 相对 v1.0 修正了 25 项审查发现（见第 0 节与 `07_Review_and_Changes_v1.1.docx`）。

---

## 0. Changes in v1.1 relative to v1.0
An independent review of the complete v1.0 pipeline covered rules, aggregation, validation code and documentation, checked against the data. It produced 25 findings (6 high severity).
- **Records.** Each finding, its evidence and its fix are in `Documentation/review_findings_v1.1.csv`.
- **Label changes.** 469 classification units (3,678 goal records) change at least one label (Strict, Extended, E, S or G). The full transition matrix is in `Documentation/version_comparison_v1.0_to_v1.1_label_transitions.csv`.
- **Rule set unchanged in principle.** The rules still never reference years or ISS categories. The same rules apply to all years.

| ID | area | severity | finding | status |
|---|---|---|---|---|
| R01 | classification | high | Bare 'governance' was Strict G, contrary to task brief 4.3 (governance must be specific) | fixed in v1.1 |
| R02 | classification | medium | ESG business lines (MSCI 'ESG segments net new sales', 'ESG-Dedicated AUM') were Strict ESG | fixed in v1.1 |
| R03 | classification | medium | 'Customer Engagement Index' was Strict S via the employee 'engagement index' rule; 'Customer/Partner Engagement' was Strict S | fixed in v1.1 |
| R04 | classification | medium | Worker radiation dose (nuclear), loss of containment, 'LCEs', 'Retention ... of high potential employees', 'Employee one-year retention' were Unknown (false negatives) | fixed in v1.1 |
| R05 | classification | medium | Spurious Unknowns: discretionary cash flow, insurance 'Individual Markets/Life' lines, strategic diversification, balance sheet, CASM/RASM, dayrates, clinical dose milestones, community count | fixed in v1.1 |
| R06 | classification | low | 'Satisfaction of strategic sales goals' (fulfilment) was Extended (customer satisfaction) | fixed in v1.1 |
| R07 | classification | low | Community Reinvestment Act results were only Extended | fixed in v1.1 |
| R08 | classification | low | Government relations were Extended (stakeholder); lobbying is not an ESG performance outcome | fixed in v1.1 |
| R09 | classification | low | 'mental health' lacked a word boundary (matched inside 'environmental health'); 'diverse' lacked one (Diversey) | fixed in v1.1 |
| R10 | logic | medium | Pillar label set to 0 although an ambiguous word for that pillar was present (e.g. 'Safety and Governance' -> G=0) | fixed in v1.1 |
| R11 | logic | medium | esg_extended_only = 1 when Strict was Unknown and Extended = 1 (should be Unknown) | fixed in v1.1 |
| R12 | logic | high | E/S/G adoption required ALL performance grants to be non-ESG for a 0; a firm with only S conditions got E = Unknown instead of 0 | fixed in v1.1 |
| R13 | logic | medium | E/S/G grant and KPI shares were published as exact although they are lower bounds (general ESG terms leave pillars unresolved) | fixed in v1.1 |
| R14 | data | medium | 144 duplicated grantIDs had conflicting performancetype ('Abs' and 'Time'; 3 also 'Rel'); v1.0 kept the first row by accident | fixed in v1.1 |
| R15 | data | medium | Grants whose declared number of objectives exceeds recorded objectives were classified 0 although the missing objectives could be ESG | fixed in v1.1 |
| R16 | measure | high | Value share used grant-date fair value only, which is missing for 98.6% of cash-incentive awards (ISS stores their target payout in nonEquityTarget); ESG sits mostly in annual cash plans, so exposure was understated | fixed in v1.1 |
| R17 | measure | low | Counts were missing (not 0) for CEOs and firm-years without grants | fixed in v1.1 |
| R18 | analysis | medium | Balanced panel selected firms whose adoption was KNOWN every year (selection on the outcome; 40% adoption) | fixed in v1.1 |
| R19 | validation | high | Scoring code had never been executed: 'U' labels broke numeric comparisons, joins used version-specific text_id, bootstrap ignored strata, kappa mishandled missing | fixed in v1.1 |
| R20 | reproducibility | medium | text_id was a sequence number (changes when units change); the frozen sample existed only in a local file with ISS text | fixed in v1.1 |
| R21 | documentation | medium | Methodology report numbers were hand-typed (would go stale after any data update); several variable definitions were blank | fixed in v1.1 |
| R22 | transparency | low | No independent check of the AGHJ implementation | fixed in v1.1 |
| R23 | data | high | Stata export forced latin-1 and replaced non-latin-1 characters (e.g. ’ —) with '?' in every string variable (found by the v1.1 audit: text_id hash check failed) | fixed in v1.1 |
| R24 | development check | high | Caught BEFORE release: in the rewritten aggregation the helper count for pillar S shared a name with the Strict count, so S adoption equalled Strict adoption | fixed in v1.1 |
| R25 | development check | medium | Caught BEFORE release by reviewing every changed unit: 'work environment' fell to the Environmental rule; 'placement' matched inside 'replacement'; specific board-governance phrases became Unknown | fixed in v1.1 |

Firm-year Strict adoption, lower bound (performance grants), v1.0 → v1.1:

| FY | Adopt lb v1.0 | Adopt lb v1.1 | S lb v1.0 | S lb v1.1 | G lb v1.0 | G lb v1.1 | Value share v1.0 | Value share v1.1 |
|---|---|---|---|---|---|---|---|---|
| 1998 | 3.2% | 3.5% | 2.9% | 3.2% | 0.0% | 0.0% | 0.0% | 0.6% |
| 2008 | 10.7% | 10.7% | 10.4% | 10.4% | 0.5% | 0.5% | 1.2% | 4.7% |
| 2015 | 14.6% | 14.8% | 13.6% | 13.9% | 1.1% | 0.9% | 0.8% | 5.9% |
| 2017 | 14.6% | 14.6% | 13.8% | 13.9% | 0.8% | 0.7% | 1.4% | 5.4% |
| 2018 | 15.5% | 15.4% | 14.7% | 14.7% | 0.7% | 0.6% | 1.6% | 6.1% |
| 2020 | 19.6% | 19.4% | 17.3% | 17.4% | 1.3% | 0.7% | 2.5% | 8.1% |
| 2021 | 30.4% | 30.4% | 25.0% | 25.0% | 1.4% | 1.1% | 4.1% | 11.7% |

## 1. Raw ISS data inventory
- **Location**: the 18 Stata files under `01. Incentive Lab/` plus the ISS User Guide (8 July 2021).
- **Inventory output**: `Documentation/data_inventory_files.csv` lists, for every file:
  - rows and columns;
  - candidate-key duplicate counts;
  - year range.

  `data_inventory_fields.csv` lists every field with its dtype, non-missing count, number of `-9999` missing codes and blanks.

Files used:

| File | Role | Rows |
|---|---|---|
| 08. Grants of Plan-Based Awards Table | grants, award attributes, performance type | 469,573 (469,429 distinct grantID) |
| 02. Absolute Performance Goals Data | goal text and payout (absolute goals) | 716,130 |
| 16. Relative Performance Goals Data | goal text and peer benchmark (relative goals) | 89,985 |
| 03. Accelerated Performance Goals Data | acceleration conditions | 7,976 |
| 12. Participant Data by Fiscal Year | identity, title, role codes, currentCEO | 474,170 |
| 05. Company Data by Fiscal Year | firm-year universe, name, ticker, CUSIP | 33,328 |

The other files (ownership, director compensation, peers, holding requirements, consultants, outstanding equity, exercises) are not needed for the construct.
- **Summary Compensation Table (file 18).** It has **no participantID column** in this delivery, although the guide lists one. It therefore cannot be linked to executives and is not used.

## 2. Source files and field definitions
Field meanings follow the ISS User Guide; the fields are listed in `data_inventory_fields.csv`. Key conventions verified in the data:
- **Missing codes.** Numeric missing values are coded `-9999.xx`, and `-99999` also occurs. They are converted to missing:
  - 25,159 `grantDateFV` values;
  - 22,968 `nonEquityTarget` values.

  Date missing values are coded `01/01/9999`; 117,906 grant dates are converted to missing. Impossible values are also set to missing (1 negative `grantDateFV`, 18 negative `vestHighGrant`).
- **Fiscal year.** Defined by ISS's 10-July rule. Goal-record `fiscalYear` equals the grant's `FiscalYear` in n/a of matched records.
- **`metricType`.** Before 2018 it takes Accounting / Other / Stock Price. From 2018 it is granular and adds Social / Environment / CSR. "Market-related" is the old "Stock Price" (User Guide).
- **`metric`.** The ESG labels (Staff Health And Safety, Diversity, Csr, Climate Change And Energy Use, …) belong to the 2018 re-taxonomy: only **58 of 10,603** rows carrying them are dated before 2018.
- **`metricOther`.** This is the descriptive text. Its blank share is a text-availability break, which is reported, not imputed:
  - **68%** of goal records in 1998;
  - **50%** in 2010;
  - **3%** in 2018;
  - **0%** in 2021.

## 3. Entity and identifier relationships
```
CompanyFY (CIK, fiscalYear) 1───* GpbaGrant (grantID; CIK, FY, FM, participantID)
ParticipantFY (CIK, FY, FM, participantID) 1───* GpbaGrant
GpbaGrant 1───* GpbaAbs / GpbaRel / GpbaAcc  (grantId, goal id, periodID)
```
- **Goal ids are recycled across grants.** `absId` alone has 191,919 duplicates and `(absId, periodID)` has 54,978. The true record key is **(goal_source, grantId, goal_id, periodId)**, which has 0 duplicates in all three goal files (asserted in Step 03).
- **Duplicated grantIDs.** 141 grantIDs occur more than once (285 rows, 144 surplus rows).
  - The rows are identical except `performancetype`, which takes conflicting values (e.g. `Abs` and `Time`).
  - Since v1.1, the type is resolved from the grant's goal records: ABS → Abs, REL → Rel, ABS+REL → AbsRel, none → Time. The grant is flagged `grant_dup_resolved`.
- **Goal-to-grant linkage.** 99.9988% of goal records match a grant. 10 records belonging to 3 grantIDs are absent from the grants table; they are listed in `Data/Intermediate/audit_goal_grants_missing_in_grant_table.csv`.
- **ParticipantFY key.** The table is unique on (CIK, FY, FM, participantID), but *not* on (CIK, FY, participantID): there are 1,007 duplicates caused by fiscal-month changes. Grants are therefore matched on all four fields. 99.975% match; 117 unmatched grants are listed in an audit file.
- **CompanyFY** is unique on (CIK, FY). 776 firm-years have no grants. Every grant firm-year exists in CompanyFY.

## 4. Definition of distinct performance KPIs
- **Raw goal record** = objective × measurement period (814,091). This level is kept in `ESG_Goal_Record_Classification.dta`.
- **KPI** = **(grantid, goal_source, text_id)**, giving 654,123 KPIs.
  - It collapses the measurement periods of the same objective (84,463 KPIs span more than one period).
  - It collapses repeated objectives with identical text in the same grant, e.g. A1 = year-1 EPS and A2 = year-2 EPS (4,849 KPIs, `kpi_duplicate_flag = 1`).
  - Absolute, relative and accelerated versions of a metric remain separate KPIs, because they are different contractual conditions.
- **No collapsing across grants or executives at KPI level.** Each executive's grant is a separate award.
- **Distinct-KPI shares at aggregate levels.** At executive, CEO and firm level, a distinct KPI is (goal_source, text_id) *within the unit*. The same metric used in the plans of five NEOs therefore counts once in the firm-year KPI share.
- **Reconciliation.** Σ `kpi_source_count` = 814,091 = number of goal records.

## 5. Grant and executive matching methodology
- **No fuzzy matching.** Grants carry CIK, fiscal year, fiscal month and participantID directly, so no cross-year or name-based matching is used.
- **Executive-firm-year** = (CIK, FY, participantID). Identity is attached by an exact 4-field match to ParticipantFY. `exec_identity_match_status` records matched_exact / partially_matched / unmatched.
- **Performance-based grant** = `performancetype` ∈ {Abs, Rel, AbsRel}; time-based = Time.
  - Hybrid absolute + relative awards are flagged (`grant_is_hybrid_absrel`, 36,356 grants).
  - Performance grants are split by payout medium. **PERF_CASH** = non-equity incentive plan awards (`paid_in_cash`). **PERF_EQUITY** = performance shares, units and options. ESG conditions are far more common in cash bonus plans (§18).
  - Time grants with acceleration conditions are flagged `grant_time_with_acceleration`. They are excluded from the performance-grant denominator, but their ACC KPIs still count as performance conditions for grant-level ESG linkage.
- **Goal availability** (`grant_goal_status`):

| Status | Meaning | Grants |
|---|---|---|
| perf_with_goals | performance grant with goal records | 233,384 |
| time_no_perf_condition | time grant (reliably no ESG condition) | 231,168 |
| time_with_accel_goals | time grant with acceleration goals | 4,496 |
| time_accel_declared_goals_missing | time grant, acceleration declared, goals missing | 171 |
| perf_goals_missing | performance grant, goal data missing (missing data ≠ no condition) | 159 |
| type_missing | performance type missing | 51 |

- **Incomplete goal data** (`grant_goal_data_incomplete`, 335 grants). ISS declares more objectives (`num_absolute` + `num_relative`) than are recorded in the goal files, by both rows and distinct objectives. Such a grant is never coded 0: without an ESG-positive recorded KPI its ESG status is Unknown, because the missing objectives could be ESG.
- **Grant value** (`grant_value_combined`, used for value shares):
  - grant-date fair value where reported;
  - otherwise the non-equity target payout of cash awards, which ISS does not value at grant date.
  - Source counts: grant date fair value 278,382; nonequity target payout 106,524; missing 84,523.
- **Date checks.** 256 grant dates fall outside [FY−3, FY+2] (`grant_date_suspect`), and 49 expiration dates precede the grant date (`grant_dates_inconsistent`). Both come from the ISS source; they are flagged, not changed.

## 6. CEO identification methodology
CEO status is read from ParticipantFY `currentCEO` (True/False). Role codes are the fallback:
- `CEO`;
- `UC` = segment CEO, never treated as company CEO;
- `FO` / `R` = former / retired.

Status of each firm-year:

| Status | Firm-years | Treatment |
|---|---|---|
| unique_current_ceo_flag | 32,231 | strict CEO sample (`ceo_strict_sample = 1`) |
| no_ceo_identified | 515 | exception table only |
| multiple_current_ceo_flags | 505 | all candidates kept; none silently selected; in exception table |
| rolecode_fallback_unique | 14 | kept as an alternative (not strict) |
| rolecode_ambiguous | 1 | exception table only |

- **Exception table.** `Data/Intermediate/audit_ceo_exceptions.csv` (1,960 rows, 1,035 firm-years). Firm-years with several `currentCEO = 1` executives keep all candidates; none is silently selected.
- **Non-CEO executives** have `currentCEO = 0` explicitly, belong to a firm-year whose CEO is identified, and are not a CEO candidate. There are 130,794 such executive-years.
- **Role unknown.** n/a executive-years have an unknown role, e.g. their firm-year has no identified CEO or their participant record is unmatched. They are excluded from non-CEO aggregates.
  - 1,043 of them sit in firm-years that also have identified non-CEO executives. They are counted there in `nonceo_n_role_unknown_execs`, with `nonceo_role_uncertainty_flag = 1`.
  - The rest belong to firm-years without a non-CEO row.

## 7. Text normalization
Applied to `metricOther`:
- NFKC normalisation;
- typographic quotes and dashes, and the source mojibake `‚Äô`, are normalised;
- whitespace is collapsed;
- trailing punctuation is stripped;
- the result is lower-cased for the key.

**Classification unit** = `metric || lower(metricOther)`. The suffix `|| ctx=` is added only when the text is blank (§11).
- There are 38,590 units. Identical text receives the identical label in every year.
- `text_id` = "T" + the first 10 hex digits of SHA-1(`text_key`). It is therefore stable across versions and re-runs, so human labels can be joined safely.

## 8. ESG construct definition
An **ESG-linked performance condition** is a performance condition whose text explicitly references an environmental, social or governance objective. The construct concerns the condition itself, not whether the firm is ESG-oriented.
- **Strict ESG**: clearly identifiable E, S or G content (§10).
- **Extended ESG** = Strict ESG plus explicitly stakeholder-oriented conditions:
  - customers;
  - product and patient safety and quality, and healthcare quality;
  - privacy and fair treatment;
  - customer-facing service reliability;
  - community engagement.
- **Invariants.** Strict = 1 implies Extended = 1 (asserted in code). `esg_extended_only` (1 / 0 / Unknown) identifies the additions.

## 9. Strict and Extended classification methodology
**Approach.** A deterministic, versioned rule engine (`Code/esg_rules.py`, `Code/classify.py`) with **57 regex rules**. The rules are exported with their rationale and their change in this version to `Dictionaries/b_revised_rules_v1.1.csv`.
- **Rule kinds:** ESG 21, EXT 9, MASKN 8, MASK 5, ADJ 5, AMB 4, NONESG 2, EXT_AMB 1, NONSPEC 1, FILLER 1.
- **Order.** Rules run in priority order, and each match *consumes* its text span so that later rules cannot reuse it:
  1. protected phrases, e.g. "safe work environment";
  2. masks for false-positive phrases; some masks also count as non-ESG evidence, e.g. "safety and soundness" or "economic environment";
  3. routed specific phrases, e.g. "product safety" or "customer engagement" → Extended, before the generic rules;
  4. Strict ESG rules: multi-pillar ESG phrases first, then E, S and G;
  5. Extended (stakeholder) rules;
  6. ambiguous rules;
  7. ESG-adjacent exclusions;
  8. non-specific placeholders;
  9. non-ESG financial / operating evidence;
  10. filler words.

**Decision.**
- **Strict** = 1 if any Strict rule fires.
- Otherwise Strict = Unknown if an ambiguous or placeholder rule fires.
- Otherwise Strict = 0 if there is **positive** non-ESG, adjacent or stakeholder evidence.
- Otherwise Strict = Unknown. Failing to find an ESG keyword is never sufficient for 0.
- **Extended** = 1 if Strict = 1 or a stakeholder rule fires. It is Unknown if Strict is Unknown or an ambiguous stakeholder rule fires. Otherwise it is 0.
- **Pillars** (E/S/G) are defined for Strict = 1 texts:
  - 1 if a rule of that pillar fired;
  - Unknown if a general ESG term (ESG, CSR, ESG ratings, bare "sustainability") fired, or if an ambiguous rule of that pillar fired, e.g. bare "governance" in "Safety and Governance" → G Unknown;
  - otherwise 0.

**`metric` × `metricOther` joint reading.** Before 2018, `metricOther` often holds only a qualifier (`metric` = Cashflow, `metricOther` = Free). The two fields are therefore read together:
- Financial standardised labels (EPS, Sales, …; available 1998–2021) count as non-ESG evidence.
- "Customer Satisfaction" counts as Extended evidence.
- Placeholder labels (Other, Individual, Vague, Operational, Non-Financial, Business Unit, Discretionary) carry no evidence.
- A financial label followed by a qualifier of at most two words (e.g. Cashflow + "Discretionary") is read as the financial metric.
- **2018-taxonomy ESG labels and ISS ESG metricTypes are never used.**

**Starting point: AGHJ (2025).** The 953 terms are reproduced verbatim, with page numbers, in `a_paper_dictionary_AGHJ2025_953.csv`.
- **Removed terms.** Only 3 of the 81 removed terms are disclosed in A.4 (complaint, cyber, trust). The other 78 are **not reconstructed**.
- **Review.** Every one of the 953 terms was reviewed against the 1998–2021 texts (`b_paper_keyword_review_v1.1.csv`):

| Decision | Keywords |
|---|---|
| no occurrence 1998 2021; not carried forward or untested | 439 |
| retained strict | 126 |
| no occurrence 1998 2021; covered by v1 rule | 112 |
| context required keyword alone insufficient; mostly non esg in context | 84 |
| context required keyword alone insufficient; mostly strict in context | 76 |
| context required keyword alone insufficient; mixed in context | 72 |
| excluded esg adjacent by definition | 18 |
| retained strict with context exclusions | 11 |
| reassigned extended only | 11 |
| excluded generic or false positive | 4 |

**New expressions.** 46 expressions not matched by any AGHJ term are listed, with their unit and row counts, in `b_new_expressions_v1.1.csv`. The decision log is `Dictionaries/c_change_log.csv`.

**No trend calibration.**
- No rule references years, ISS categories or trend targets.
- Rule development used frequency-ranked and random reviews of all years jointly.
- The v1.1 review checked every unit whose label changed relative to v1.0 (`Validation/version_changed_units_*_local.csv`).

## 10. E, S and G coding rules (summary; exact regex in `b_revised_rules_v1.1.csv`)
**Environmental (E):**
- GHG, carbon, CO2, methane, SF6, NOx, SO2, flaring, LDAR, scope 1–3, net zero, scrubbers, science-based targets
- Climate change, action, risk or policy; TCFD
- Renewable energy *adoption*, carbon-free capacity share, electrification, energy-use/intensity reduction
- Water use and quality, wastewater
- Waste, recycling, plastics, landfill, coal ash
- Spills and environmental releases
- The word "environmental" (business senses of "environment" are masked); biodiversity, reclamation, pollution

**Social (S):**
- Occupational, process and public safety: safety, TRIR, DART, OSHA, lost time, fatalities, SIF, vehicle accidents, near misses, HSE/EHS/EH&S, process safety, loss of containment, worker radiation exposure, gas leaks/damage prevention, wildfire mitigation, NRC findings, workers' compensation claims
- DEI, including supplier diversity and health equity
- Specific human capital: engagement/satisfaction surveys, voluntary or employee turnover, retention of talent, training programmes, wellbeing, mental health, work environment, human capital
- Community investment, volunteering, philanthropy
- Defined social-access goals: affordable-housing goals, duty to serve, financial inclusion, Community Reinvestment Act
- Human rights, labour standards, animal welfare

**Governance (G):** specific content only:
- ethics, code of conduct, anti-corruption/bribery, FCPA, whistle-blowing;
- corporate governance, board composition/diversity/evaluation, shareholder rights, say-on-pay, governance ratings.

Bare "governance" is ambiguous and therefore Unknown, because portfolio, project and data governance also exist.

**General (multi-pillar):**
- ESG, CSR, corporate citizenship and ESG ratings (DJSI, GRESB, Sustainalytics, CDP, GRI): Strict = 1, with E/S/G **Unknown** unless a pillar term co-occurs.
- "Sustainability" is treated as a qualifier when it accompanies a pillar term, e.g. "Environmental Sustainability" → E only.

## 11. Treatment of ambiguous and generic metrics
- **Placeholders** → Unknown: Individual Performance, Strategic Objectives, Corporate Goals, Discretionary, Non-Financial, Other, Leadership, Operational Goals, Scorecard. They remain Unknown even when a financial term co-occurs, e.g. "EPS and Individual Performance".
- **Ambiguous** terms → Strict Unknown:
  - energy efficiency / DSM (an environmental vs an operating-cost objective);
  - bare "water", "waste", "green", "clean", "renewables";
  - notices of violation without environmental context;
  - bare "integrity", "social", "turnover", "attrition", "governance".
- **ESG-adjacent but excluded by definition** (Strict 0, Extended 0, flagged in `adjacent_flags`):
  - generic compliance, regulatory exams, risk management, internal controls, SOX, audit, cybersecurity, AML/BSA;
  - generic talent, succession, leadership development, culture, HR, hiring, teamwork, collective bargaining;
  - government relations / public affairs;
  - ESG business lines (ESG fund sales or assets);
  - renewable-energy business-line execution (wind/solar projects, renewable portfolio growth).
- **Blank text** (`metric` and `metricOther` both blank or placeholder):
  - 60,986 goal rows are overwhelmingly pre-2018 relative TSR / stock-price goals. Their *time-consistent* financial metricType (Accounting; Stock Price = Market-related) is admitted as **structured context** → 0, with `classification_method = structured_context` and medium confidence. The text-only label is kept separately as Unknown (`esg_strict_textonly`).
  - Other blank units → Unknown (`no_text`).
  - Blank units with a 2018 ESG label → Unknown (`iss_esg_label_only`).
- **Mixed texts** ("EPS and Safety") → Strict = 1, flagged `mixed_esg_and_financial_text`. 4 units with an ESG term under a financial `metric` label are flagged `esg_term_under_financial_label` for review.

## 12. Classification verification results
**Development (completed).** Rules were developed on all years jointly by:
- reviewing the AGHJ keywords that occur in the data, with their most frequent and their non-ISS matches;
- reviewing the top Unknown, Strict = 1, Extended-only and ambiguous units by frequency;
- reviewing random samples of low-frequency Strict = 1 units and of Strict = 0 units;
- reviewing all paper-versus-revised disagreements;
- for v1.1, reviewing every unit whose label changed relative to v1.0.

Each error found led to a rule change, documented in `c_change_log.csv` and `b_revised_rules_v1.1.csv` (`version_change`).

**Independent validation.**
- **Sample.** 601 units drawn under v1.0 with seed 20261031 across 32 strata: period of use (pre-2018 only / post-2018 only / both) × predicted class (Strict / Extended-only / non-ESG / Unknown) × frequency (1 / 2–9 / 10+ rows).
- **Never redrawn.** The sample is frozen under v1.0, and every later classifier version is scored on the same probability sample.
- **Weights.** Each unit is sampled once, so repeated descriptions are not double counted. Unit weights are N_h/n_h; row weights are N_h/n_h × n_goal_rows.
- **Materials.**
  - blind coding sheets for two coders;
  - the answer key (local only);
  - `Validation/CODING_GUIDELINES.md`;
  - a review queue of frequent Unknown and conflicting units (not part of the validation sample).
- **Scoring (Step 13).** Computed for the current version and for v1.0:
  - precision, recall, F1, FPR, FNR and Unknown rate by period, dimension and frequency;
  - stratum weights, with stratified bootstrap CIs over units;
  - Cohen's kappa, with Unknown as its own category.
- **Current status:** Every label comes from the deterministic classifier v1.1. No adjudicated human reference labels exist yet, so **no accuracy statistic is reported**. The blind validation sample (601 units, frozen under v1.0), the coding guideline and the scoring code are ready (§12).

**Comparison with AGHJ (2025)** (`Validation/e_*.csv`; goal-record level, 1998–2021):

|  | v1.1 Strict = 1 | v1.1 Strict = 0 | v1.1 Unknown |
|---|---|---|---|
| AGHJ = 1 (53,123 rows) | 29,442 | 16,773 | 6,908 |
| AGHJ = 0 (760,968 rows) | 677 | 651,211 | 109,080 |

The 23,681 AGHJ-positive goal rows that v1.1 does **not** classify as Strict ESG fall into these mutually exclusive unit categories:

| Category | Units | Goal rows |
|---|---|---|
| Extended-only (customer retention, SAIDI, patient satisfaction …) | 382 | 3,112 |
| ESG-adjacent by definition (regulatory compliance, succession, culture …) | 930 | 5,306 |
| Unknown, no adjacent flag (e.g. 'Leadership', 'Integrity', 'Energy efficiency') | 1,117 | 6,705 |
| Generic or false positive (cost/debt 'reduction', 'policies in force', company names …) | 1,512 | 8,558 |

- **Additional Strict ESG.** In the other direction, v1.1 identifies 100 units (677 rows) as Strict ESG that no AGHJ term matches.
- **No Unknown state in AGHJ.** The AGHJ method treats blank `metricOther` as non-ESG, and that covers up to 68% of rows in early years.

**Replication benchmark.** `Validation/e_paper_replication_benchmark.csv` reproduces the AGHJ (2025) Table 1 series with our implementation of their keyword method:
- unit: executive-years with performance-based pay;
- an executive-year counts as ESG if any metric text contains an AGHJ keyword.

This checks how our implementation of their method compares with their published series. It is not a validation of our classifier.

| FY | Executive-years (ours) | AGHJ method, our data | AGHJ Table 1 (published) | v1.1 Strict lb, our data |
|---|---|---|---|---|
| 2008 | 5,450 | 20.5% | 22.9% | 11.7% |
| 2009 | 5,263 | 23.8% | 29.0% | 17.0% |
| 2010 | 5,960 | 22.0% | 36.6% | 13.9% |
| 2011 | 6,674 | 21.7% | 20.2% | 14.4% |
| 2012 | 7,332 | 24.2% | 26.8% | 14.9% |
| 2013 | 7,918 | 22.7% | 27.1% | 12.9% |
| 2014 | 8,517 | 23.2% | 29.9% | 14.0% |
| 2015 | 8,721 | 24.0% | 20.4% | 14.3% |
| 2016 | 9,318 | 24.6% | 23.7% | 15.6% |
| 2017 | 10,056 | 23.5% | 23.8% | 15.5% |
| 2018 | 10,206 | 24.8% | 24.9% | 16.1% |
| 2019 | 10,475 | 25.9% | 29.6% | 16.5% |
| 2020 | 10,564 | 29.9% | 32.1% | 20.6% |
| 2021 | 9,951 | 40.2% | 45.4% | 32.3% |

- **Where it matches.** Our implementation is within 3 pp of the published series in 2008, 2011, 2012, 2016, 2017, 2018, 2020.
- **Why the published series is noisy before 2018.** It rests on only n/a observations per year (Table 1, "# Metrics"), compared with several thousand executive-years in ours.
- **Other sources of difference:**
  - sample construction (their merge with ExecuComp and other filters);
  - the 78 undisclosed removed terms.

## 13. Missingness and coverage
Goal-record level (`Annual_Analysis/annual_text_coverage.csv`):

| Year | Goal rows | metricOther blank | v1.1 Strict Unknown share | ISS ESG share (diag) |
|---|---|---|---|---|
| 1998 | 11,768 | 68% | 21% | 0.0% |
| 2003 | 14,068 | 62% | 22% | 0.0% |
| 2008 | 37,493 | 55% | 14% | 0.0% |
| 2013 | 46,929 | 49% | 13% | 0.0% |
| 2017 | 48,305 | 34% | 13% | 0.1% |
| 2018 | 46,425 | 3% | 12% | 4.2% |
| 2021 | 44,200 | 0% | 12% | 8.7% |

Despite the very different blank-text rates, Unknown shares are similar across years. Blank financial-label rows are informative, and structured context is used.

At unit level, adoption Unknown is large: one unresolved KPI in any performance grant leaves a non-adopting unit Unknown, and annual bonus plans often contain "Individual performance". Hence:
- every share is published with `_lb` / `_ub` and coverage;
- adoption is reported as lower bound / complete-case / upper bound.

## 14. Exact numerator / denominator definitions
Full details are in `Documentation/variable_dictionary.csv`. It gives the formula, numerator, denominator, values, missing interpretation and source for all 567 variables.

**Grant ESG**
- 1 = ≥1 KPI is ESG.
- 0 = all KPIs are 0, or the grant is a time grant with no performance condition.
- `.` otherwise. This includes performance grants with missing goal data and grants with incomplete goal data (§5).

**Adoption (unit)**
- 1 = ≥1 grant in the universe is 1.
- 0 = all grants are 0.
- `.` otherwise, or empty universe.
- Universes: ALL grants / PERF grants / PERF_CASH / PERF_EQUITY.

**Pillar adoption**
- 1 = ≥1 grant has a confirmed E (S, G) condition.
- 0 = every performance grant has that pillar = 0.
- `.` otherwise.

**Grant share** (= #ESG grants / #grants in universe)
- Published only if #unknown = 0.
- `_lb` = #ESG / N; `_ub` = (#ESG + #unknown) / N; coverage = #known / N.

**KPI share** (= #distinct ESG KPIs / #distinct KPIs), with the same exact / lb / ub rule.

**E/S/G grant and KPI shares** (= #performance grants with a confirmed E (S, G) condition / #performance grants)
- `_lb` counts pillar-Unknown as 0 and `_ub` counts it as 1.
- The exact share requires every pillar to be known.

**Value share**
- = Σ value of grants containing ≥1 Strict ESG condition / Σ value of grants with reported value.
- Value = `grant_value_combined`: grant-date fair value, or else the non-equity target payout.
- **This is not value attributable to ESG.** ISS `percentVest` is the share of the award per *measurement period*. It interacts with AND/OR performance groupings and "extra" adjustments (User Guide pp. 4–6). Reliable KPI weights are therefore not observable, and none are fabricated.

## 15. Dataset observation counts and 16. Primary keys
Also in `Documentation/dataset_summary.csv`. Every key was verified unique and non-missing on re-read (Step 16).

| Dataset | Obs | Vars | Primary key | Years |
|---|---|---|---|---|
| A `ESG_Text_Dictionary.dta` | 38,590 | 43 | text_id | 1998–2021 |
| B `ESG_KPI_Master.dta` | 654,123 | 38 | kpi_id | 1998–2021 |
| (B-alt) `ESG_Goal_Record_Classification.dta` | 814,091 | 29 | goal_record_id | 1998–2021 |
| C `ESG_Grant_Master.dta` | 469,429 | 82 | grantid | 1998–2021 |
| D `ESG_Executive_Firm_Year.dta` | 164,832 | 96 | cik + fiscalyear + participantid | 1998–2021 |
| E `ESG_CEO_Firm_Year.dta` | 33,278 | 99 | cik + fiscalyear + participantid | 1998–2021 |
| F `ESG_Firm_Year_Master.dta` | 33,328 | 94 | cik + fiscalyear | 1998–2021 |
| G `ESG_NonCEO_Firm_Year.dta` | 31,944 | 86 | cik + fiscalyear | 1998–2021 |

**Stata names.** Names are ≤ 32 characters.
- Overlong preferred names are shortened by a fixed rule, e.g. `_extended` → `_ext`, `classification` → `class`, `_strict` → `_str`, `_grant_share` → `_gshr`.
- The mapping is in the variable dictionary (`preferred_name`).
- Strings are stored as UTF-8.

## 17. Matching and reconciliation statistics
| Check | Result |
|---|---|
| Goal records → grant | 99.9988% matched (10 records, 3 grants unmatched) |
| Grants → ParticipantFY (exact 4 keys) | 99.975% matched (117 unmatched) |
| Grants → CompanyFY firm-year | 100% (asserted) |
| Σ KPI source rows = goal records | 814,091 = 814,091 |
| Σ grant KPIs = KPI master (matched grants); esg + non-esg + unknown = n_kpis per grant | asserted |
| Σ executive grants = Σ firm grants = grant master | 469,429 |
| Firm ESG / perf / all grant counts = Σ over executive-years | asserted for every firm-year |
| Shares in [0,1]; lb ≤ ub; exact = lb when complete; cash + equity ≤ perf; pillar adoption ⇒ Strict adoption | asserted (Steps 08–11) and re-checked (Step 16) |
| Strict = 1 ⇒ Extended = 1 | asserted; 0 violations |

All of these are asserted in code; any failure stops the pipeline. The independent quality audit (Step 16) re-derives grant ESG, unit counts, adoption, E/S/G adoption and lb shares from the lower-level data in the final `.dta` files.
- Result: 95 checks: PASS 79, FAIL 0, WARN 2, INFO 14.
- Details: `Documentation/quality_audit_results.csv`.

## 18. Annual ESG trends
Full tables are in `Annual_Analysis/`:
- `annual_firm_year.csv`, `annual_executive_year.csv`, `annual_ceo_year_strict_sample.csv`;
- `annual_cash_vs_equity_firm.csv`.

Firm-years with performance grants, Strict ESG adoption:

| FY | Firms | Adopt lb | Complete-case | Adopt ub | Extended lb | Mean perf-grant share lb | Mean perf coverage | ISS ESG (diag) |
|---|---|---|---|---|---|---|---|---|
| 1998 | 689 | 3.5% | 6.5% | 49.5% | 6.1% | 2.1% | 0.61 | 0.0% |
| 2003 | 772 | 4.0% | 8.7% | 57.9% | 6.6% | 2.9% | 0.55 | 0.0% |
| 2008 | 1,236 | 10.7% | 20.9% | 59.5% | 14.9% | 5.4% | 0.68 | 0.0% |
| 2013 | 1,278 | 13.1% | 27.0% | 64.4% | 17.6% | 6.6% | 0.70 | 0.0% |
| 2015 | 1,263 | 14.8% | 34.3% | 71.7% | 18.8% | 7.1% | 0.67 | 0.0% |
| 2016 | 1,200 | 14.1% | 32.2% | 70.3% | 18.2% | 6.6% | 0.69 | 0.1% |
| 2017 | 1,188 | 14.6% | 29.0% | 64.4% | 19.2% | 6.7% | 0.73 | 0.3% |
| 2018 | 1,160 | 15.4% | 30.5% | 64.9% | 20.2% | 7.5% | 0.74 | 13.7% |
| 2019 | 1,128 | 16.8% | 31.8% | 64.0% | 21.5% | 7.9% | 0.76 | 16.8% |
| 2020 | 1,090 | 19.4% | 37.1% | 67.0% | 24.5% | 9.4% | 0.75 | 19.3% |
| 2021 | 956 | 30.4% | 52.8% | 72.8% | 34.9% | 14.2% | 0.78 | 30.1% |

Firm-level pillar adoption (lb):

| Pillar | 2015 | 2017 | 2018 | 2020 | 2021 |
|---|---|---|---|---|---|
| E | 4.1% | 4.5% | 5.5% | 5.9% | 9.4% |
| S | 13.9% | 13.9% | 14.7% | 17.4% | 25.0% |
| G | 1.0% | 0.7% | 0.6% | 0.7% | 1.2% |

Executive level, Strict adoption lb (CEO strict sample in parentheses):

| Year | Executives (CEO) |
|---|---|
| 2015 | 13.8% (13.0%) |
| 2017 | 13.7% (13.3%) |
| 2018 | 14.8% (14.7%) |
| 2020 | 18.7% (18.5%) |
| 2021 | 29.4% (29.7%) |

Cash bonus plans versus equity performance awards (firm-years, Strict adoption lb within each universe):

| FY | Firms with perf grants | ESG in any perf grant | ESG in a cash incentive award | ESG in an equity performance award |
|---|---|---|---|---|
| 2008 | 1,236 | 10.7% | 10.1% | 1.1% |
| 2015 | 1,263 | 14.8% | 14.7% | 0.8% |
| 2017 | 1,188 | 14.6% | 13.8% | 1.9% |
| 2018 | 1,160 | 15.4% | 14.8% | 1.9% |
| 2020 | 1,090 | 19.4% | 18.2% | 3.1% |
| 2021 | 956 | 30.4% | 28.0% | 5.3% |

## 19. Interpretation of the 2018 classification change
1. **The rise survives uniform text classification, but the 2018 jump does not.**
   - ISS's own ESG categories move from 0.3% (2017) to 13.7% (2018) of firm-years.
   - Uniform text classification moves only from 14.6% to 15.4%.
   - At KPI level, text-Strict ESG KPIs number 1,640 in 2017 and 1,665 in 2018 (`break_iss_vs_text_kpi_2014_2021.csv`).
   - The real increase is concentrated in 2020–2021: 19.4% → 30.4%.
2. **The ISS re-classification created an artificial break.**

| FY | ISS-ESG KPIs: text Strict 1 | text Strict 0 | text Unknown | ISS non-ESG KPIs: text Strict 1 |
|---|---|---|---|---|
| 2014 | 0 | 0 | 0 | 1,535 |
| 2015 | 0 | 0 | 0 | 1,700 |
| 2016 | 30 | 0 | 5 | 1,656 |
| 2017 | 28 | 0 | 0 | 1,612 |
| 2018 | 1,385 | 153 | 149 | 280 |
| 2019 | 1,576 | 251 | 176 | 228 |
| 2020 | 1,979 | 203 | 161 | 319 |
| 2021 | 2,972 | 323 | 276 | 433 |

3. **Sample composition is not the explanation.**
   - 1,134 firms continue from 2017 to 2018; their adoption goes from 14.1% to 15.3%.
   - 54 firms exit and 26 enter.
   - Balanced panel: firms with performance grants in every year 2015–2021 (845 firms). Its Strict adoption is:

| FY | Adopt lb | Complete-case | Adopt ub | Unknown |
|---|---|---|---|---|
| 2015 | 14.4% | 32.6% | 70.2% | 55.7% |
| 2016 | 14.6% | 33.5% | 71.1% | 56.6% |
| 2017 | 15.1% | 30.2% | 65.0% | 49.8% |
| 2018 | 16.2% | 31.5% | 64.7% | 48.5% |
| 2019 | 17.8% | 32.8% | 63.7% | 45.9% |
| 2020 | 20.1% | 38.1% | 67.3% | 47.2% |
| 2021 | 31.0% | 53.6% | 73.1% | 42.1% |

4. **Extensive vs intensive margin** (mean firm perf-grant ESG share, lb; Shapley-type split):

| Period | Δ mean share | Extensive | Intensive |
|---|---|---|---|
| 2015-2017 | -0.3 pp | -0.1 pp | -0.2 pp |
| 2017-2018 | +0.8 pp | +0.4 pp | +0.3 pp |
| 2018-2021 | +6.7 pp | +7.2 pp | -0.4 pp |
| 2017-2021 | +7.5 pp | +7.4 pp | +0.1 pp |

   From 2018 to 2021 the mean share rises by +6.7 pp; +7.2 pp comes from more firms adopting (extensive margin) and -0.4 pp from higher intensity among adopters.
5. **Pillars.** Social conditions, mainly safety and DEI, drive the level and the increase. Environmental and governance conditions are listed in the pillar table of §18.
6. **Coverage.** Classification coverage of performance grants (mean firm-level) is 0.61 in 1998, 0.73 in 2017, 0.74 in 2018 and 0.78 in 2021. There is no discontinuity at 2018.
   - The pre-2018 text-availability problem (blank `metricOther`) mainly affects financial-label rows. These remain classifiable from the time-consistent `metric` label.

These are descriptive measurement results, not causal effects.

## 20. Limitations and recommended research uses
- **Provisional labels.** Every label comes from the deterministic classifier v1.1. No adjudicated human reference labels exist yet, so **no accuracy statistic is reported**. The blind validation sample (601 units, frozen under v1.0), the coding guideline and the scoring code are ready (§12).
  - The human review queue (`Validation/human_review_queue_v1.1_local.csv`, 1,001 frequent Unknown or conflicting units) can resolve many Unknowns.
  - Adjudicated labels are applied by re-running Step 06 onward, which records `human_reviewed`.
- **Wide Unknown band.** It comes from non-specific annual-bonus metrics.
  - Use `_lb` / `_ub` and coverage.
  - Report complete-case estimates as a robustness check, or condition on `*_esg_measurement_complete = 1`.
  - Never treat `.` as 0.
- **Definitional choices** are documented and switchable:
  - generic compliance/risk/cyber and generic talent/succession are excluded (`adjacent_flags`);
  - customer service reliability is Extended-only;
  - renewable business-line execution is excluded.

  Researchers who prefer other boundaries can re-define them using `esg_topics` / `adjacent_flags` in Dataset A.
- **No ESG-attributable value.** The value-share measures are exposure measures: the value of grants *containing* ESG conditions.
- **CEO identification** relies on ISS `currentCEO`. Co-CEO and succession years are kept in the exception table, not resolved.
- **Software.** Datasets are built in Python (pandas) and written as labelled Stata 118 `.dta` files (accepted by the user). Stata `.do` versions were not produced because Stata is not available in the build environment.
- **Licensing.** ISS data and any file containing ISS text are git-ignored and must not be redistributed: `Data/`, `*_local.csv`, `Dictionaries/local/`, `*_local.docx`.

**Recommended primary variables (firm-year):**
- `firm_perf_esg_adopt_strict`;
- `firm_esg_perf_share_lb` / `_ub` (with `firm_perf_class_coverage`);
- `firm_esg_kpi_share_lb` / `_ub`;
- `firm_esg_[e|s|g]_adopt`;
- the Extended counterparts and the cash / equity split as robustness checks.
