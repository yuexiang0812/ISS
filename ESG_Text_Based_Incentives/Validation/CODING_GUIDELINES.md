# Human coding guidelines — ESG performance-metric validation

**Purpose.** Produce *independent* reference labels for the 601 classification units of the validation sample. The rule-based classifier is then validated against them.
- The sample was drawn under classifier v1.0 after its rules were frozen, and it is **never redrawn**. Every later classifier version (currently the one in `Code/config.py`, `CLASSIFIER_VERSION`) is scored on this same probability sample.
- Step 13 also scores v1.0's predictions, so the two versions can be compared.
- Coders must **not** look at the model labels, the rule files or the answer key (`validation_sample_v1.0_KEY_local.csv`) before submitting their labels.

## Files
| File | Use |
|---|---|
| `validation_coding_sheet_v1.0_coder1_local.csv` / `..._coder2_local.csv` | Blind sheets: one row per unit (metric label + representative `metricOther` text, years and number of firms). Created once and never overwritten |
| `human_labels/coder1_labels.csv`, `human_labels/coder2_labels.csv` | Save each completed sheet here. **Keep the `sample_id` column** (the `text_id` printed on the sheet is also accepted) |
| `human_labels/adjudication_sheet_local.csv` | Written by Step 13 once both coder files exist. Agreements are pre-filled; the cells of disagreements are empty and marked `disagree_* = 1` |
| `human_labels/adjudicated_labels.csv` | Final labels after a third person resolves the disagreements. Columns: an identifier (`sample_id` preferred; `text_key` or `text_id` also accepted) + `human_esg_strict, human_esg_extended, human_esg_e, human_esg_s, human_esg_g` (+ `reviewer, review_date`) |
| `human_review_queue_<version>_local.csv` | **Not part of validation.** Frequent unresolved or flagged texts to review when improving the rules. Confirmed labels may be added to `adjudicated_labels.csv` by `text_key` |

**Identifiers.** Every identifier is mapped to the stable `text_key`, so a label stays attached to its text even if the classifier changes. The loader accepts, per row:
- `sample_id` (V0001 …);
- `text_key`;
- the current `text_id` (T + 10 hex digits);
- the v1.0 sheet `text_id` (T + 6 digits).

A row that matches no text stops the pipeline with an error.

## Coding values
For each label, enter `1`, `0` or `U`.
- `1`: the text gives enough evidence that this is the case.
- `0`: the text gives enough evidence that it is not.
- `U`: the text is insufficient to decide.

Blank cells count as `U`; any other value is rejected. `h_confidence` takes `high`, `medium` or `low`. Use `h_notes` for the reason in any non-obvious case.

Code **the performance condition described by the text**. Do not code the company, its industry, or what you believe the firm intended.

**Consistency rules.** These follow from the definitions and are applied automatically when labels are loaded:

| Rule | What happens |
|---|---|
| Strict = 1 ⇒ Extended = 1 | Extended is set to 1 |
| Extended = 0 ⇒ Strict = 0 | Strict is set to 0 |
| Strict = 0 ⇒ E = S = G = 0 | Pillar cells may be left blank |
| Strict = U ⇒ E, S, G = U | Pillar cells may be left blank |
| Strict = 1 ⇒ pillars as coded | Blank pillar = U |
| E, S or G = 1 while Strict ≠ 1 | **Error.** Stops the run and lists the rows, because it is contradictory |
| Strict = 1 with E = S = G = 0 | **Error.** Stops the run and lists the rows |

Every automatic fix is counted in `Logs/06_dataset_A_text_dictionary.log`.

## Definitions (identical to the classifier's construct)

**Strict ESG = 1** if the metric is an explicitly environmental, social or governance performance condition.

**Environmental (E):**
- GHG / carbon / methane emissions and intensity, science-based targets
- Climate targets or policies
- Air pollutants, spills and releases, coal ash
- Environmental compliance, incidents or violations
- Waste, recycling, plastics
- Water use and water quality
- Biodiversity, land reclamation
- Renewable or low-carbon energy *adoption*
- Energy-use reduction, but only when the text gives an environmental rationale

**Social (S):**
- Occupational, process and public safety: TRIR, DART, lost time, fatalities, vehicle accidents, near misses, HSE / EHS, loss of containment, worker radiation exposure, workers' compensation claims
- Diversity, equity and inclusion, including supplier diversity and health equity
- *Specific* employee engagement, satisfaction, retention, turnover, training/development, wellbeing, work environment
- Human rights, labour standards, animal welfare
- Community investment, volunteering, philanthropy
- Clearly defined social-access mission goals, e.g. affordable-housing goals, financial inclusion, Community Reinvestment Act results

**Governance (G):** specific governance content only.
- Business ethics, code of conduct, anti-corruption / bribery, whistle-blowing
- Corporate governance, board composition / diversity / evaluation / board-governance processes, shareholder rights, say-on-pay, governance ratings
- Bare "governance" is **not** enough. It can mean portfolio, project or data governance, so code it `U`.

**General ESG:** "ESG", "CSR", "sustainability", ESG ratings (DJSI, GRESB …). Code Strict = 1. Code E/S/G = `U` unless a specific pillar is named.

**Extended ESG = 1** if Strict = 1, **or** the metric is an explicit stakeholder condition:
- Customer / client / patient satisfaction, experience, engagement, retention, complaints, NPS. Customer engagement is Extended, not employee engagement.
- Product, food or patient safety and product quality
- Healthcare quality-of-care measures, e.g. Medicare STARS
- Data privacy, fair lending, affordability for customers
- Utility service reliability to customers (SAIDI / SAIFI / outage duration)
- Community or stakeholder engagement without a defined welfare outcome

**Code 0 (not ESG) for:**
- Financial, market and operating metrics: EPS, EBITDA, revenue, TSR, cost reduction, production, efficiency, "Operational Excellence" with a financial meaning
- Product development and regulatory approvals, e.g. FDA submissions
- Bank "safety and soundness"; clinical "safety and efficacy" data; insurance "accident-year combined ratio"
- Generic compliance, risk management, internal controls, SOX, audit, cybersecurity
- Generic talent management, succession planning, leadership development, culture, hiring, collective bargaining
- Government relations / public affairs / lobbying
- ESG *business lines*, e.g. sales of ESG funds or ESG-dedicated assets under management
- Renewable-energy project execution or portfolio growth, i.e. a business line
- Company or segment names that happen to contain ESG words, e.g. "Clean Energy Businesses EBITDA", "Peoples Gas", "Diversey"
- "Satisfaction of" in the sense of *fulfilment*, e.g. "satisfaction of strategic sales goals"

**Code U (unknown) for:**
- Placeholders: Individual Performance, Strategic Objectives, Corporate Goals, Discretionary, Non-Financial, Other, Leadership (alone), Operational Goals, Scorecard
- Texts too ambiguous to decide: "Water", "Energy Efficiency" with no environmental context, "Integrity", bare "Governance", "Notices of Violation" with no environmental context
- A blank text with a placeholder label

**Mixed texts:** if *any* component of the text is an ESG condition (e.g. "EPS and Safety"), code Strict = 1.

## Process
1. **Code independently.** Two coders code independently and fill the `coder_id` column.
2. **Agreement and adjudication sheet.** Save the sheets as `human_labels/coder1_labels.csv` and `coder2_labels.csv`, then run:

   ```bash
   python Code/master_run.py 13
   ```

   Step 13 reports agreement and Cohen's kappa per label (Unknown counts as its own category) and writes `human_labels/adjudication_sheet_local.csv`.
3. **Adjudicate.** A third reviewer resolves every disagreement and every `U` versus `0`/`1` conflict. Save the completed sheet as `human_labels/adjudicated_labels.csv`.
4. **Apply and score.** Run:

   ```bash
   python Code/master_run.py 06
   ```

   - Step 06 applies the adjudicated labels: `human_reviewed = 1`, status `confirmed` (or `confirmed_unknown` for a human `U`). The model's own labels stay in the `*_model` columns.
   - Steps 07–11 propagate the labels.
   - Step 13 computes precision, recall, F1, FPR, FNR and the Unknown rate. These are reported for the current version and for v1.0, with stratum weights and stratified bootstrap CIs.
   - Step 18 regenerates every report.
5. **Never change the sample.** It was drawn **after** the v1.0 rules were frozen (rules MD5 is stored in the key file), and it must never be redrawn once coding has started.
