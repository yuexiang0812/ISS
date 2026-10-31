# ESG_Text_Based_Incentives

This project builds a time-consistent, text-based measure of ESG-linked executive incentives from ISS Incentive Lab data covering 1998–2021. The classifier is version v1.0 and its labels are **provisional until the human validation is completed**.

Read first: [`Documentation/Methodology_and_Validation_Report.md`](Documentation/Methodology_and_Validation_Report.md).

## Reproduce
```bash
pip install pandas numpy pyarrow        # plus poppler-utils for pdftotext
```
```bash
export ISS_RAW_DIR="/path/to/01. Incentive Lab"
```
```bash
export PAPER_PDF="/path/to/ESG_Metrics_Paper.pdf"
```
```bash
cd Code && python master_run.py         # or: python master_run.py 06   (restart from step 06)
```

## Layout
| Folder | Content |
|---|---|
| `Code/` | Pipeline steps `01`–`15`, `master_run.py`. The rule dictionary is in `esg_rules.py` and the engine in `classify.py`; `aggregate.py` holds the shared measure definitions |
| `Dictionaries/` | Deliverables (a)–(c): (a) the AGHJ (2025) 953 keywords; (b) the revised rules, the review of every paper keyword, and new expressions; (c) the change log |
| `Data/Intermediate/` | Parquet intermediates and audit tables. Git-ignored because they contain ISS data |
| `Data/Final/` | The 7 required `.dta` datasets plus `ESG_Goal_Record_Classification.dta`. Git-ignored |
| `Validation/` | Deliverable (e), part 1: the paper-vs-revised comparison. Also the blind validation sample, coding guidelines, the review queue and the scoring code. Files ending in `_local.csv` contain ISS text and are git-ignored |
| `Annual_Analysis/` | Annual trends for 1998–2021 and the 2018-break analysis |
| `Documentation/` | The report, `variable_dictionary.csv` (459 variables), `dataset_summary.csv` and the data inventory |
| `Logs/` | One log per step, plus `master_run.log` |

## Deliverables (a)–(e) of the dictionary task
| Deliverable | Files |
|---|---|
| (a) original paper dictionary | `Dictionaries/a_paper_dictionary_AGHJ2025_953.csv`, `a_paper_removed_keywords_examples_A4.csv` |
| (b) revised dictionary | `Dictionaries/b_revised_rules_v1.0.csv`, `b_paper_keyword_review_v1.0.csv`, `b_new_expressions_v1.0.csv` |
| (c) change log | `Dictionaries/c_change_log.csv` |
| (d) KPI-level results and reasons | `Data/Final/ESG_KPI_Master.dta`, `ESG_Goal_Record_Classification.dta`, `ESG_Text_Dictionary.dta`. See the `classification_reason` and `rule_ids` columns |
| (e) comparison and validation | `Validation/e_*.csv`, `Validation/validation_status_v1.0.json`, and report §12 |
