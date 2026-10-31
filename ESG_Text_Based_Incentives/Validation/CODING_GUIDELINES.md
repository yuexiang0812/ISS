# Human coding guidelines — ESG performance-metric validation (classifier v1.0)

**Purpose.** Produce *independent* reference labels for 601 randomly sampled classification units, so that the frozen
rule-based classifier (v1.0) can be validated. Coders must **not** look at the model labels, the rule files or the
answer key (`validation_sample_v1.0_KEY_local.csv`) before submitting their labels.

## Files
| File | Use |
|---|---|
| `validation_coding_sheet_v1.0_coder1_local.csv` / `..._coder2_local.csv` | Blind sheets: one row per unit (metric label + representative `metricOther` text, years and number of firms) |
| `human_labels/coder1_labels.csv`, `human_labels/coder2_labels.csv` | Save each completed sheet here (keep `text_id`) |
| `human_labels/adjudicated_labels.csv` | Final labels after a third person resolves coder disagreements. Columns: `text_id, human_esg_strict, human_esg_extended, human_esg_e, human_esg_s, human_esg_g, reviewer, review_date` |
| `human_review_queue_v1.0_local.csv` | **Not part of validation.** These are frequent unresolved or flagged texts, to be reviewed when building v1.1 |

After the labels are in place, re-run `python Code/master_run.py 06`. Step 06 applies the adjudicated labels (`human_reviewed = 1`, status `confirmed`). Step 13 then computes the validation statistics, comparing the *v1.0 model labels* with the human reference.

## Coding values
For each label, enter `1`, `0` or `U`.
- `1`: the text gives enough evidence that this is the case.
- `0`: the text gives enough evidence that it is not.
- `U`: the text is insufficient to decide.

`h_confidence` takes `high`, `medium` or `low`. Use `h_notes` for the reason in any non-obvious case.

Code **the performance condition described by the text**. Do not code the company, its industry, or what you believe the firm intended.

## Definitions (identical to the classifier's construct)

**Strict ESG = 1** if the metric is an explicitly environmental, social or governance performance condition.

**Environmental (E):**
- GHG / carbon / methane emissions and intensity
- Climate targets or policies
- Air pollutants, spills and releases
- Environmental compliance, incidents or violations
- Waste, recycling, plastics
- Water use and water quality
- Biodiversity, land reclamation
- Renewable or low-carbon energy *adoption*
- Energy-use reduction, but only when the text gives an environmental rationale

**Social (S):**
- Occupational, process and public safety: TRIR, DART, lost time, fatalities, vehicle accidents, near misses, HSE / EHS
- Diversity, equity and inclusion, including supplier diversity
- *Specific* employee engagement, satisfaction, retention, turnover, training/development, wellbeing
- Human rights and labour standards
- Community investment, volunteering, philanthropy
- Clearly defined social-access mission goals (e.g. affordable-housing goals)

**Governance (G):**
- Business ethics, code of conduct, anti-corruption / bribery, whistle-blowing
- Corporate governance
- Board composition, diversity and evaluation

**General ESG:** "ESG", "CSR", "sustainability", ESG ratings (DJSI, GRESB …). Code Strict = 1. Code E/S/G = `U` unless a specific pillar is named.

**Extended ESG = 1** if Strict = 1, **or** the metric is an explicit stakeholder condition:
- Customer / client / patient satisfaction, experience, retention, complaints, NPS
- Product, food or patient safety and product quality
- Healthcare quality-of-care measures
- Data privacy, fair lending, affordability for customers
- Utility service reliability to customers (SAIDI / SAIFI / outage duration)
- Community or stakeholder engagement without a defined welfare outcome

**Code 0 (not ESG) for:**
- Financial, market and operating metrics: EPS, EBITDA, revenue, TSR, cost reduction, production, efficiency, "Operational Excellence" with a financial meaning
- Product development and regulatory approvals, e.g. FDA submissions
- Bank "safety and soundness"
- Clinical "safety and efficacy" data
- Insurance "accident-year combined ratio"
- Generic compliance, risk management, internal controls, SOX, audit, cybersecurity
- Generic talent management, succession planning, leadership development, culture, hiring
- Renewable-energy project execution or portfolio growth, i.e. a business line
- Company or segment names that happen to contain ESG words (e.g. "Clean Energy Businesses EBITDA", "Peoples Gas")

**Code U (unknown) for:**
- Placeholders: Individual Performance, Strategic Objectives, Corporate Goals, Discretionary, Non-Financial, Other, Leadership (alone), Operational Goals, Scorecard
- Texts too ambiguous to decide, e.g. "Water", "Energy Efficiency" with no environmental context, "Integrity", "Notices of Violation" with no environmental context
- A blank text with a placeholder label

**Mixed texts:** if *any* component of the text is an ESG condition (e.g. "EPS and Safety"), code Strict = 1.

## Process
1. Two coders code independently. Use the `coder_id` column.
2. Report Cohen's kappa; step 13 computes it automatically.
3. A third reviewer adjudicates every disagreement and every `U` versus `0`/`1` conflict.
4. Do not change the sample. It was drawn **after** the rules were frozen (rules MD5 is stored in the key file), and it must never be redrawn once coding has started.
