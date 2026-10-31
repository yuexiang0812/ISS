# Text-Based ESG Executive Incentives from ISS Incentive Lab (1998–2021)
## Measurement Methodology and Validation Report — classifier {{version}}

> **Generated file — do not edit by hand.** `Code/18_build_reports.py` rebuilds this report from the current pipeline outputs on every run. The narrative lives in `Code/docgen/methodology_template.md`; every number is read from the outputs named in each section. Generated {{generated}} (git {{commit}}).

> **Status: {{validation_label}}.** {{validation_en}}

{{narrative_checks}}

### 中文摘要
- **范围与方法**：对 ISS Incentive Lab 1998–2021 年全部 {{n_goal_records}} 条业绩目标记录，用同一套文本规则（{{version}}，{{n_rules}} 条规则）做 ESG 分类，产出 KPI、Grant、高管、CEO、非 CEO 和公司-年层面的数据集。
  - 每个标签都是 1 / 0 / 未知三态：只有找到明确的非 ESG 证据才记 0，找不到 ESG 关键词本身不等于 0。
  - ISS 自带的 ESG 分类（metricType 与 2018 年新增的 metric 标签）只用于诊断对比，从不作为分类依据。
- **2018 年的跳升来自 ISS 改分类**：按 ISS 原分类，含 ESG 条件的公司-年比例从 2017 年的 {{iss_2017}} 跳到 2018 年的 {{iss_2018}}。按统一文本分类，业绩型 grant 的公司-年 Strict ESG 采用率下界只从 {{lb_2017}} 变为 {{lb_2018}}。
- **真正的上升在 2020–2021 年**：采用率下界 2020 年为 {{lb_2020}}，2021 年为 {{lb_2021}}。增长主要来自新采用的公司（广延边际），社会类（S）条件占主体。
- **未知比例如实报告**：许多年度奖金指标（如 "Individual Performance"）无法判断是否属于 ESG。因此每个比例都给出下界 lb（未知按 0）、完整样本 cc 和上界 ub（未知按 1）。
- **验证状态**：{{validation_cn}}
- **本版本修改**：{{version}} 相对 {{prev_version}} 修正了 {{n_findings}} 项审查发现（见第 0 节与 `07_Review_and_Changes_{{version}}.docx`）。

---

## 0. Changes in {{version}} relative to {{prev_version}}
An independent review of the complete {{prev_version}} pipeline covered rules, aggregation, validation code and documentation, checked against the data. It produced {{n_findings}} findings ({{n_findings_high}} high severity).
- **Records.** Each finding, its evidence and its fix are in `Documentation/review_findings_{{version}}.csv`.
- **Label changes.** {{n_units_changed}} classification units ({{n_rows_changed}} goal records) change at least one label (Strict, Extended, E, S or G). The full transition matrix is in `Documentation/version_comparison_{{prev_version}}_to_{{version}}_label_transitions.csv`.
- **Rule set unchanged in principle.** The rules still never reference years or ISS categories. The same rules apply to all years.

{{table:review_findings}}

Firm-year Strict adoption, lower bound (performance grants), {{prev_version}} → {{version}}:

{{table:version_firm_compare}}

## 1. Raw ISS data inventory
- **Location**: the 18 Stata files under `01. Incentive Lab/` plus the ISS User Guide (8 July 2021).
- **Inventory output**: `Documentation/data_inventory_files.csv` lists, for every file:
  - rows and columns;
  - candidate-key duplicate counts;
  - year range.

  `data_inventory_fields.csv` lists every field with its dtype, non-missing count, number of `-9999` missing codes and blanks.

Files used:

{{table:inventory}}

The other files (ownership, director compensation, peers, holding requirements, consultants, outstanding equity, exercises) are not needed for the construct.
- **Summary Compensation Table (file 18).** It has **no participantID column** in this delivery, although the guide lists one. It therefore cannot be linked to executives and is not used.

## 2. Source files and field definitions
Field meanings follow the ISS User Guide; the fields are listed in `data_inventory_fields.csv`. Key conventions verified in the data:
- **Missing codes.** Numeric missing values are coded `-9999.xx`, and `-99999` also occurs. They are converted to missing:
  - {{n_fv_missing_code}} `grantDateFV` values;
  - {{n_net_missing_code}} `nonEquityTarget` values.

  Date missing values are coded `01/01/9999`; {{n_grantdate_missing_code}} grant dates are converted to missing. Impossible values are also set to missing ({{n_neg_fv}} negative `grantDateFV`, {{n_neg_vest}} negative `vestHighGrant`).
- **Fiscal year.** Defined by ISS's 10-July rule. Goal-record `fiscalYear` equals the grant's `FiscalYear` in {{fy_match_share}} of matched records.
- **`metricType`.** Before 2018 it takes Accounting / Other / Stock Price. From 2018 it is granular and adds Social / Environment / CSR. "Market-related" is the old "Stock Price" (User Guide).
- **`metric`.** The ESG labels (Staff Health And Safety, Diversity, Csr, Climate Change And Energy Use, …) belong to the 2018 re-taxonomy: only **{{n_esg_label_pre2018}} of {{n_esg_label_rows}}** rows carrying them are dated before 2018.
- **`metricOther`.** This is the descriptive text. Its blank share is a text-availability break, which is reported, not imputed:
  - **{{blank_1998}}** of goal records in 1998;
  - **{{blank_2010}}** in 2010;
  - **{{blank_2018}}** in 2018;
  - **{{blank_2021}}** in 2021.

## 3. Entity and identifier relationships
```
CompanyFY (CIK, fiscalYear) 1───* GpbaGrant (grantID; CIK, FY, FM, participantID)
ParticipantFY (CIK, FY, FM, participantID) 1───* GpbaGrant
GpbaGrant 1───* GpbaAbs / GpbaRel / GpbaAcc  (grantId, goal id, periodID)
```
- **Goal ids are recycled across grants.** `absId` alone has {{dup_absid}} duplicates and `(absId, periodID)` has {{dup_absid_period}}. The true record key is **(goal_source, grantId, goal_id, periodId)**, which has 0 duplicates in all three goal files (asserted in Step 03).
- **Duplicated grantIDs.** {{n_dup_grant_ids}} grantIDs occur more than once ({{n_dup_grant_rows}} rows, {{n_dup_grant_surplus}} surplus rows).
  - The rows are identical except `performancetype`, which takes conflicting values (e.g. `Abs` and `Time`).
  - Since {{version}}, the type is resolved from the grant's goal records: ABS → Abs, REL → Rel, ABS+REL → AbsRel, none → Time. The grant is flagged `grant_dup_resolved`.
- **Goal-to-grant linkage.** {{goal_match_share}} of goal records match a grant. {{n_goal_unmatched}} records belonging to {{n_goal_unmatched_grants}} grantIDs are absent from the grants table; they are listed in `Data/Intermediate/audit_goal_grants_missing_in_grant_table.csv`.
- **ParticipantFY key.** The table is unique on (CIK, FY, FM, participantID), but *not* on (CIK, FY, participantID): there are {{dup_pfy_3key}} duplicates caused by fiscal-month changes. Grants are therefore matched on all four fields. {{grant_pfy_match_share}} match; {{n_grant_pfy_unmatched}} unmatched grants are listed in an audit file.
- **CompanyFY** is unique on (CIK, FY). {{n_fy_no_grants}} firm-years have no grants. Every grant firm-year exists in CompanyFY.

## 4. Definition of distinct performance KPIs
- **Raw goal record** = objective × measurement period ({{n_goal_records}}). This level is kept in `ESG_Goal_Record_Classification.dta`.
- **KPI** = **(grantid, goal_source, text_id)**, giving {{n_kpis}} KPIs.
  - It collapses the measurement periods of the same objective ({{n_kpi_multiperiod}} KPIs span more than one period).
  - It collapses repeated objectives with identical text in the same grant, e.g. A1 = year-1 EPS and A2 = year-2 EPS ({{n_kpi_dupobj}} KPIs, `kpi_duplicate_flag = 1`).
  - Absolute, relative and accelerated versions of a metric remain separate KPIs, because they are different contractual conditions.
- **No collapsing across grants or executives at KPI level.** Each executive's grant is a separate award.
- **Distinct-KPI shares at aggregate levels.** At executive, CEO and firm level, a distinct KPI is (goal_source, text_id) *within the unit*. The same metric used in the plans of five NEOs therefore counts once in the firm-year KPI share.
- **Reconciliation.** Σ `kpi_source_count` = {{n_kpi_source_rows}} = number of goal records.

## 5. Grant and executive matching methodology
- **No fuzzy matching.** Grants carry CIK, fiscal year, fiscal month and participantID directly, so no cross-year or name-based matching is used.
- **Executive-firm-year** = (CIK, FY, participantID). Identity is attached by an exact 4-field match to ParticipantFY. `exec_identity_match_status` records matched_exact / partially_matched / unmatched.
- **Performance-based grant** = `performancetype` ∈ {Abs, Rel, AbsRel}; time-based = Time.
  - Hybrid absolute + relative awards are flagged (`grant_is_hybrid_absrel`, {{n_hybrid}} grants).
  - Performance grants are split by payout medium. **PERF_CASH** = non-equity incentive plan awards (`paid_in_cash`). **PERF_EQUITY** = performance shares, units and options. ESG conditions are far more common in cash bonus plans (§18).
  - Time grants with acceleration conditions are flagged `grant_time_with_acceleration`. They are excluded from the performance-grant denominator, but their ACC KPIs still count as performance conditions for grant-level ESG linkage.
- **Goal availability** (`grant_goal_status`):

{{table:goal_status}}

- **Incomplete goal data** (`grant_goal_data_incomplete`, {{n_goal_incomplete}} grants). ISS declares more objectives (`num_absolute` + `num_relative`) than are recorded in the goal files, by both rows and distinct objectives. Such a grant is never coded 0: without an ESG-positive recorded KPI its ESG status is Unknown, because the missing objectives could be ESG.
- **Grant value** (`grant_value_combined`, used for value shares):
  - grant-date fair value where reported;
  - otherwise the non-equity target payout of cash awards, which ISS does not value at grant date.
  - Source counts: {{value_source_counts}}.
- **Date checks.** {{n_date_suspect}} grant dates fall outside [FY−3, FY+2] (`grant_date_suspect`), and {{n_date_inconsistent}} expiration dates precede the grant date (`grant_dates_inconsistent`). Both come from the ISS source; they are flagged, not changed.

## 6. CEO identification methodology
CEO status is read from ParticipantFY `currentCEO` (True/False). Role codes are the fallback:
- `CEO`;
- `UC` = segment CEO, never treated as company CEO;
- `FO` / `R` = former / retired.

Status of each firm-year:

{{table:ceo_status}}

- **Exception table.** `Data/Intermediate/audit_ceo_exceptions.csv` ({{n_ceo_exc_rows}} rows, {{n_ceo_exc_fy}} firm-years). Firm-years with several `currentCEO = 1` executives keep all candidates; none is silently selected.
- **Non-CEO executives** have `currentCEO = 0` explicitly, belong to a firm-year whose CEO is identified, and are not a CEO candidate. There are {{n_nonceo_execyears}} such executive-years.
- **Role unknown.** {{n_role_unknown}} executive-years have an unknown role, e.g. their firm-year has no identified CEO or their participant record is unmatched. They are excluded from non-CEO aggregates.
  - {{n_role_unknown_in_g}} of them sit in firm-years that also have identified non-CEO executives. They are counted there in `nonceo_n_role_unknown_execs`, with `nonceo_role_uncertainty_flag = 1`.
  - The rest belong to firm-years without a non-CEO row.

## 7. Text normalization
Applied to `metricOther`:
- NFKC normalisation;
- typographic quotes and dashes, and the source mojibake `‚Äô`, are normalised;
- whitespace is collapsed;
- trailing punctuation is stripped;
- the result is lower-cased for the key.

**Classification unit** = `metric || lower(metricOther)`. The suffix `|| ctx=` is added only when the text is blank (§11).
- There are {{n_units}} units. Identical text receives the identical label in every year.
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
**Approach.** A deterministic, versioned rule engine (`Code/esg_rules.py`, `Code/classify.py`) with **{{n_rules}} regex rules**. The rules are exported with their rationale and their change in this version to `Dictionaries/b_revised_rules_{{version}}.csv`.
- **Rule kinds:** {{rule_kinds}}.
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
- **Review.** Every one of the 953 terms was reviewed against the 1998–2021 texts (`b_paper_keyword_review_{{version}}.csv`):

{{table:keyword_review}}

**New expressions.** {{n_new_expr}} expressions not matched by any AGHJ term are listed, with their unit and row counts, in `b_new_expressions_{{version}}.csv`. The decision log is `Dictionaries/c_change_log.csv`.

**No trend calibration.**
- No rule references years, ISS categories or trend targets.
- Rule development used frequency-ranked and random reviews of all years jointly.
- The {{version}} review checked every unit whose label changed relative to {{prev_version}} (`Validation/version_changed_units_*_local.csv`).

## 10. E, S and G coding rules (summary; exact regex in `b_revised_rules_{{version}}.csv`)
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
  - {{n_rows_structured}} goal rows are overwhelmingly pre-2018 relative TSR / stock-price goals. Their *time-consistent* financial metricType (Accounting; Stock Price = Market-related) is admitted as **structured context** → 0, with `classification_method = structured_context` and medium confidence. The text-only label is kept separately as Unknown (`esg_strict_textonly`).
  - Other blank units → Unknown (`no_text`).
  - Blank units with a 2018 ESG label → Unknown (`iss_esg_label_only`).
- **Mixed texts** ("EPS and Safety") → Strict = 1, flagged `mixed_esg_and_financial_text`. {{n_esg_under_fin}} units with an ESG term under a financial `metric` label are flagged `esg_term_under_financial_label` for review.

## 12. Classification verification results
**Development (completed).** Rules were developed on all years jointly by:
- reviewing the AGHJ keywords that occur in the data, with their most frequent and their non-ISS matches;
- reviewing the top Unknown, Strict = 1, Extended-only and ambiguous units by frequency;
- reviewing random samples of low-frequency Strict = 1 units and of Strict = 0 units;
- reviewing all paper-versus-revised disagreements;
- for {{version}}, reviewing every unit whose label changed relative to {{prev_version}}.

Each error found led to a rule change, documented in `c_change_log.csv` and `b_revised_rules_{{version}}.csv` (`version_change`).

**Independent validation.**
- **Sample.** {{valid_n}} units drawn under {{sample_version}} with seed 20261031 across {{valid_strata}} strata: period of use (pre-2018 only / post-2018 only / both) × predicted class (Strict / Extended-only / non-ESG / Unknown) × frequency (1 / 2–9 / 10+ rows).
- **Never redrawn.** The sample is frozen under {{sample_version}}, and every later classifier version is scored on the same probability sample.
- **Weights.** Each unit is sampled once, so repeated descriptions are not double counted. Unit weights are N_h/n_h; row weights are N_h/n_h × n_goal_rows.
- **Materials.**
  - blind coding sheets for two coders;
  - the answer key (local only);
  - `Validation/CODING_GUIDELINES.md`;
  - a review queue of frequent Unknown and conflicting units (not part of the validation sample).
- **Scoring (Step 13).** Computed for the current version and for {{prev_version}}:
  - precision, recall, F1, FPR, FNR and Unknown rate by period, dimension and frequency;
  - stratum weights, with stratified bootstrap CIs over units;
  - Cohen's kappa, with Unknown as its own category.
- **Current status:** {{validation_en}}

**Comparison with AGHJ (2025)** (`Validation/e_*.csv`; goal-record level, 1998–2021):

{{table:overlap_rows}}

The {{n_paper_pos_not_strict}} AGHJ-positive goal rows that {{version}} does **not** classify as Strict ESG fall into these mutually exclusive unit categories:

{{table:disagreement}}

- **Additional Strict ESG.** In the other direction, {{version}} identifies {{n_rev_only_units}} units ({{n_rev_only_rows}} rows) as Strict ESG that no AGHJ term matches.
- **No Unknown state in AGHJ.** The AGHJ method treats blank `metricOther` as non-ESG, and that covers up to {{blank_1998}} of rows in early years.

**Replication benchmark.** `Validation/e_paper_replication_benchmark.csv` reproduces the AGHJ (2025) Table 1 series with our implementation of their keyword method:
- unit: executive-years with performance-based pay;
- an executive-year counts as ESG if any metric text contains an AGHJ keyword.

This checks how our implementation of their method compares with their published series. It is not a validation of our classifier.

{{table:replication}}

- **Where it matches.** Our implementation is within 3 pp of the published series in {{replication_close_years}}.
- **Why the published series is noisy before 2018.** It rests on only {{aghj_n_range_pre2018}} observations per year (Table 1, "# Metrics"), compared with several thousand executive-years in ours.
- **Other sources of difference:**
  - sample construction (their merge with ExecuComp and other filters);
  - the 78 undisclosed removed terms.

## 13. Missingness and coverage
Goal-record level (`Annual_Analysis/annual_text_coverage.csv`):

{{table:text_coverage}}

Despite the very different blank-text rates, Unknown shares are similar across years. Blank financial-label rows are informative, and structured context is used.

At unit level, adoption Unknown is large: one unresolved KPI in any performance grant leaves a non-adopting unit Unknown, and annual bonus plans often contain "Individual performance". Hence:
- every share is published with `_lb` / `_ub` and coverage;
- adoption is reported as lower bound / complete-case / upper bound.

## 14. Exact numerator / denominator definitions
Full details are in `Documentation/variable_dictionary.csv`. It gives the formula, numerator, denominator, values, missing interpretation and source for all {{n_variables}} variables.

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

{{table:datasets}}

**Stata names.** Names are ≤ 32 characters.
- Overlong preferred names are shortened by a fixed rule, e.g. `_extended` → `_ext`, `classification` → `class`, `_strict` → `_str`, `_grant_share` → `_gshr`.
- The mapping is in the variable dictionary (`preferred_name`).
- Strings are stored as UTF-8.

## 17. Matching and reconciliation statistics
{{table:reconciliation}}

All of these are asserted in code; any failure stops the pipeline. The independent quality audit (Step 16) re-derives grant ESG, unit counts, adoption, E/S/G adoption and lb shares from the lower-level data in the final `.dta` files.
- Result: {{audit_summary}}.
- Details: `Documentation/quality_audit_results.csv`.

## 18. Annual ESG trends
Full tables are in `Annual_Analysis/`:
- `annual_firm_year.csv`, `annual_executive_year.csv`, `annual_ceo_year_strict_sample.csv`;
- `annual_cash_vs_equity_firm.csv`.

Firm-years with performance grants, Strict ESG adoption:

{{table:annual_firm}}

Firm-level pillar adoption (lb):

{{table:pillars}}

Executive level, Strict adoption lb (CEO strict sample in parentheses):

{{table:exec_ceo}}

Cash bonus plans versus equity performance awards (firm-years, Strict adoption lb within each universe):

{{table:cash_equity}}

## 19. Interpretation of the 2018 classification change
1. **The rise survives uniform text classification, but the 2018 jump does not.**
   - ISS's own ESG categories move from {{iss_2017}} (2017) to {{iss_2018}} (2018) of firm-years.
   - Uniform text classification moves only from {{lb_2017}} to {{lb_2018}}.
   - At KPI level, text-Strict ESG KPIs number {{kpi_strict_2017}} in 2017 and {{kpi_strict_2018}} in 2018 (`break_iss_vs_text_kpi_2014_2021.csv`).
   - The real increase is concentrated in 2020–2021: {{lb_2020}} → {{lb_2021}}.
2. **The ISS re-classification created an artificial break.**

{{table:break_kpi}}

3. **Sample composition is not the explanation.**
   - {{n_continuing}} firms continue from 2017 to 2018; their adoption goes from {{cont_2017}} to {{cont_2018}}.
   - {{n_exits}} firms exit and {{n_entrants}} enter.
   - Balanced panel: firms with performance grants in every year 2015–2021 ({{n_balanced}} firms). Its Strict adoption is:

{{table:balanced}}

4. **Extensive vs intensive margin** (mean firm perf-grant ESG share, lb; Shapley-type split):

{{table:margins}}

   {{margin_sentence}}
5. **Pillars.** Social conditions, mainly safety and DEI, drive the level and the increase. Environmental and governance conditions are listed in the pillar table of §18.
6. **Coverage.** Classification coverage of performance grants (mean firm-level) is {{cov_1998}} in 1998, {{cov_2017}} in 2017, {{cov_2018}} in 2018 and {{cov_2021}} in 2021. There is no discontinuity at 2018.
   - The pre-2018 text-availability problem (blank `metricOther`) mainly affects financial-label rows. These remain classifiable from the time-consistent `metric` label.

These are descriptive measurement results, not causal effects.

## 20. Limitations and recommended research uses
- **Provisional labels.** {{validation_en}}
  - The human review queue (`Validation/human_review_queue_{{version}}_local.csv`, {{n_review_queue}} frequent Unknown or conflicting units) can resolve many Unknowns.
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
