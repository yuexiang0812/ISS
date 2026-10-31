"""Step 07 — Dataset B: ESG_KPI_Master.dta.

中文说明：KPI = 同一 grant 内、同一目标文件（绝对/相对/加速）、同一文本单元的目标；多个业绩期与同文本的重复目标合并为一个 KPI，
并保留 kpi_source_count、kpi_duplicate_flag 以及全部原始 goal id / period id，便于追溯。同时输出原始目标记录层分类（另一种表示）。
v1.1 起额外保留“仅文本”标签 kpi_esg_strict_textonly / kpi_esg_extended_textonly（不使用结构化上下文）。

KPI definition (economically distinct KPI within an award):
  kpi = (grantid, goal_source, text_id)
  * collapses multiple measurement periods of the same objective (periodId = repeated measurement, ISS Guide p.6);
  * collapses repeated objectives with identical text inside the same grant (e.g. A1 = year-1 EPS, A2 = year-2 EPS),
    flagged by kpi_duplicate_flag = 1;
  * keeps absolute vs relative vs accelerated versions of the same metric as different KPIs (different contracts);
  * does NOT collapse across grants or executives (each grant is a separate contractual award).
Alternative representation retained: ESG_Goal_Record_Classification.dta (one row per raw goal record).
"""
import numpy as np, pandas as pd
from config import INTER, get_logger, check_unique
from dtautil import write_dta

log = get_logger("07_dataset_B_kpi")
g = pd.read_parquet(INTER / "goal_records.parquet")
A = pd.read_parquet(INTER / "dataset_A.parquet")
lab = ["esg_strict", "esg_extended", "esg_extended_only", "esg_e", "esg_s", "esg_g", "esg_general", "esg_strict_textonly", "esg_extended_textonly", "classification_status",
       "classification_confidence", "classification_method", "human_reviewed", "text_key", "classification_reason"]
g = g.drop(columns=["text_key"], errors="ignore").merge(A[["text_id"] + lab], on="text_id", how="left", validate="m:1")
assert g.esg_strict.notna().sum() + g.esg_strict.isna().sum() == len(g)

# ---- raw goal-record representation (deliverable d at the most granular level)
R = g[["goal_record_id", "goal_source", "grantId", "goal_id", "periodId", "CIK", "fiscalYear", "fiscalMonth", "participantId",
       "metricType", "metric", "metricOther", "text_id", "text_key", "esg_strict", "esg_extended", "esg_extended_only", "esg_e",
       "esg_s", "esg_g", "classification_status", "classification_method", "classification_confidence", "classification_reason",
       "iss_esg_flag", "percentVest", "vestLow", "vestHigh", "goal_grant_matched"]].rename(columns=str.lower)
R = R.rename(columns={"grantid": "grantid", "metrictype": "metrictype_original", "iss_esg_flag": "iss_esg_flag_diag"})
write_dta(R, "ESG_Goal_Record_Classification.dta",
          dict(goal_record_id="Raw goal record id: source_grant_goalid_period", goal_source="ABS absolute / REL relative / ACC accelerated",
               grantid="ISS grantID", goal_id="ISS absId/relId/accId (recycled across grants)", periodid="ISS periodID (-1 = missing)",
               cik="Company CIK (from grants table)", fiscalyear="Fiscal year", fiscalmonth="Fiscal month", participantid="ISS participantID",
               metrictype_original="ISS metricType (diagnostic only)", metric="ISS metric label", metricother="ISS metricOther (raw)",
               esg_strict="Strict ESG 1/0/.", esg_extended="Extended ESG 1/0/.", iss_esg_flag_diag="DIAGNOSTIC ISS ESG metricType/label",
               percentvest="ISS percentVest (share of award per period; -9999 codes -> .)", goal_grant_matched="1 if grantId found in grants table"),
          log, keys=["goal_record_id"])

# ---- KPI collapse
g["kpi_id"] = g.goal_source + "_" + g.grantId.astype("int64").astype(str) + "_" + g.text_id
agg = g.groupby("kpi_id").agg(
    grantid=("grantId", "first"), goal_source=("goal_source", "first"), text_id=("text_id", "first"),
    goal_id=("goal_id", "min"), n_goal_ids=("goal_id", "nunique"), n_periods=("periodId", "nunique"), kpi_source_count=("goal_record_id", "size"),
    goal_ids_list=("goal_id", lambda s: "|".join(map(str, sorted(set(s.astype("int64")))))),
    period_ids_list=("periodId", lambda s: "|".join(map(str, sorted(set(s))))),
    participantid=("participantId", "first"), cik=("CIK", "first"), fiscalyear=("fiscalYear", "first"), fiscalmonth=("fiscalMonth", "first"),
    metric=("metric", "first"), metricother=("metricOther", "first"),
    metrictype_original=("metricType", lambda s: s.mode().iat[0] if len(s) else ""),
    n_metrictype_values=("metricType", "nunique"), iss_esg_flag_diag=("iss_esg_flag", "max"),
    percentvest_sum=("percentVest", lambda s: s.sum(min_count=1)), goal_grant_matched=("goal_grant_matched", "min"),
).reset_index()
K = agg.merge(A[["text_id"] + lab], on="text_id", how="left", validate="m:1")
K = K.rename(columns={c: "kpi_" + c for c in ["esg_strict", "esg_extended", "esg_extended_only", "esg_e", "esg_s", "esg_g", "esg_general", "esg_strict_textonly", "esg_extended_textonly",
                                                 "classification_status", "classification_confidence", "classification_method", "human_reviewed",
                                                 "classification_reason"]})
K["kpi_duplicate_flag"] = (K.n_goal_ids > 1).astype("int8")
K["kpi_key_complete"] = (K[["grantid", "cik", "fiscalyear", "participantid"]].notna().all(axis=1) & (K.goal_grant_matched == 1)).astype("int8")
K["kpi_iss_esg_flag_diag"] = K.pop("iss_esg_flag_diag")
check_unique(K, ["kpi_id"], "KPI master", log)
check_unique(K, ["grantid", "goal_source", "text_id"], "KPI master (components)", log)
assert K.kpi_source_count.sum() == len(g), "KPI source count does not reconcile to goal records"
log.info(f"reconciliation: sum(kpi_source_count) = {K.kpi_source_count.sum():,} = goal records {len(g):,}")
log.info(f"KPIs: {len(K):,}; duplicate-objective KPIs: {int(K.kpi_duplicate_flag.sum()):,}; multi-period KPIs: {int((K.n_periods>1).sum()):,}; "
         f"incomplete keys: {int((K.kpi_key_complete==0).sum())}")
log.info("kpi strict by year:\n" + pd.crosstab(K.fiscalyear, K.kpi_esg_strict.fillna(-1)).to_string())
K.to_parquet(INTER / "dataset_B.parquet", index=False)
L = dict(kpi_id="KPI id = goal_source_grantid_text_id", grantid="ISS grantID", goal_source="ABS/REL/ACC goal file",
         text_id="Text unit id (Dataset A)", goal_id="Representative (min) ISS objective id", n_goal_ids="Number of ISS objective ids collapsed",
         n_periods="Number of measurement periods collapsed", kpi_source_count="Number of raw goal records collapsed",
         goal_ids_list="All ISS objective ids collapsed", period_ids_list="All periodIDs collapsed", participantid="ISS participantID (grant)",
         cik="Company CIK", fiscalyear="Fiscal year", fiscalmonth="Fiscal month", metric="ISS metric label", metricother="ISS metricOther (raw)",
         metrictype_original="ISS metricType (modal; diagnostic only)", n_metrictype_values="Distinct metricType values across periods",
         percentvest_sum="Sum of ISS percentVest over collapsed records (NOT a KPI weight)", goal_grant_matched="1 if grant found in grants table",
         text_key="Standardized text key", kpi_esg_strict="Strict ESG KPI 1/0/.", kpi_esg_extended="Extended ESG KPI 1/0/.",
         kpi_esg_extended_only="Extended-only KPI 1/0/.", kpi_esg_e="Environmental KPI 1/0/.", kpi_esg_s="Social KPI 1/0/.", kpi_esg_g="Governance KPI 1/0/.",
         kpi_esg_general="Multi-pillar ESG term present", kpi_classification_status="confirmed/provisional/unknown",
         kpi_classification_confidence="high/medium/low/human", kpi_classification_method="Classification method", kpi_human_reviewed="1 if human-adjudicated",
         kpi_classification_reason="Rules fired and matched text", kpi_esg_strict_textonly="Strict ESG from text only (no structured context) 1/0/.", kpi_esg_extended_textonly="Extended ESG from text only 1/0/.", kpi_duplicate_flag="1 if identical text repeated across >1 objective in grant",
         kpi_key_complete="1 if grant, CIK, year, participant all present and grant matched", kpi_iss_esg_flag_diag="DIAGNOSTIC: any ISS ESG metricType/label")
write_dta(K, "ESG_KPI_Master.dta", L, log, keys=["kpi_id"])
