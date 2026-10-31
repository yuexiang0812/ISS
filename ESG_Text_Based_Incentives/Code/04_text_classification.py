"""Step 04 — Text classification.

中文说明：把全部目标记录归并为“分类单元”（metric + 标准化 metricOther [+ 空白文本时的结构化上下文]），
对每个单元同时运行修订后的分类器与论文 953 词基准，并把单元编号写回每条目标记录。
text_id 由 text_key 的 SHA-1 哈希生成（v1.1 起），因此与版本、数据排序无关，人工标注可跨版本对接。

1. Build classification units (Dataset A unit): (metric, metricOther_norm, ctx_key)
   ctx_key is non-empty only when metricOther is blank and metric is a placeholder label; it then holds
   the time-consistent metricType group (FIN / NONFIN / ISSESG) admitted as structured context.
2. Apply the revised classifier (current CLASSIFIER_VERSION) and the AGHJ (2025) 953-keyword baseline to every unit.
3. Write: unit-level classification (intermediate), per-goal-record classification (deliverable d),
   paper keyword diagnostics + keyword-level decision table (deliverables b/c inputs).
"""
import hashlib
import numpy as np, pandas as pd
from config import INTER, DICT, FIN_METRICTYPES, ISS_2018_ESG_METRIC_LABELS, CLASSIFIER_VERSION, get_logger
from classify import text_id_for, classify_unit, PLACEHOLDER_LABELS
from textmatch import match_terms
import esg_rules

log = get_logger("04_text_classification")
g = pd.read_parquet(INTER / "goal_records.parquet").drop(columns=["text_id"], errors="ignore")
blank = g.metricOther_norm.eq("")
ph = g.metric.isin(PLACEHOLDER_LABELS | ISS_2018_ESG_METRIC_LABELS)
g["ctx_key"] = ""
g.loc[blank & ph, "ctx_key"] = np.where(g.loc[blank & ph, "metricType"].isin(FIN_METRICTYPES), "FIN_METRICTYPE", "NONFIN_METRICTYPE")
g.loc[blank & g.metric.isin(ISS_2018_ESG_METRIC_LABELS), "ctx_key"] = "ISS_ESG_LABEL_ONLY"
g["text_key"] = g.metric + " || " + g.metricOther_norm.str.lower() + np.where(g.ctx_key != "", " || ctx=" + g.ctx_key, "")

# representative original text = most frequent raw spelling within the unit
rep = (g.groupby(["text_key", "metricOther"]).size().reset_index(name="n").sort_values(["text_key", "n"], ascending=[True, False])
         .drop_duplicates("text_key").set_index("text_key").metricOther)
u = (g.groupby("text_key").agg(metric=("metric", "first"), metricOther_norm=("metricOther_norm", "first"), ctx_key=("ctx_key", "first"),
                               metricType_mode=("metricType", lambda s: s.mode().iat[0] if len(s) else ""),
                               first_year=("fiscalYear", "min"), last_year=("fiscalYear", "max"), n_goal_rows=("goal_record_id", "size"),
                               n_grants=("grantId", "nunique"), n_firms=("CIK", "nunique"),
                               n_rows_pre2018=("fiscalYear", lambda s: int((s < 2018).sum())),
                               iss_esg_share=("iss_esg_flag", "mean"))
       .reset_index())
u["text_original"] = u.text_key.map(rep)
# lower-cased normalized text for case-variant units must classify identically -> classify on lowercase+metric
assert u.text_key.is_unique
u = u.sort_values(["first_year", "text_key"]).reset_index(drop=True)
# v1.1: stable identifier = hash of the standardized key (independent of version / ordering / data additions)
u.insert(0, "text_id", u.text_key.map(text_id_for))
assert u.text_id.is_unique, "text_id hash collision"
log.info(f"classification units: {len(u):,} (blank-text context units: {(u.ctx_key != '').sum()})")

ctx_type = {"FIN_METRICTYPE": "Accounting", "NONFIN_METRICTYPE": "Other", "ISS_ESG_LABEL_ONLY": "Social", "": ""}
res = [classify_unit(m, o.lower(), ctx_type[c]) for m, o, c in zip(u.metric, u.metricOther_norm, u.ctx_key)]
u = pd.concat([u, pd.DataFrame(res)], axis=1)
u["classifier_version"] = CLASSIFIER_VERSION

# ---- AGHJ (2025) baseline: literal 953-keyword match on metricOther (paper's field)
kd = pd.read_csv(DICT / "a_paper_dictionary_AGHJ2025_953.csv")
u["paper_terms"] = ["|".join(x) for x in match_terms(u.metricOther_norm.tolist(), kd.keyword.tolist())]
u["paper_esg"] = np.where(u.metricOther_norm.eq(""), np.nan, (u.paper_terms != "").astype(float))  # blank text: paper cannot classify
u["paper_esg_as_used"] = (u.paper_terms != "").astype(int)   # paper treats no-match/blank as non-ESG
u.to_parquet(INTER / "text_units_classified.parquet", index=False)

g = g.drop(columns=[c for c in ["text_id", "text_key_x", "text_key_y"] if c in g.columns]).merge(u[["text_key", "text_id"]], on="text_key", how="left", validate="m:1")
assert g.text_id.notna().all()
g.to_parquet(INTER / "goal_records.parquet", index=False)

# ---- summaries
def st(x): return x.map({1: "1", 0: "0"}).fillna("Unknown")
for col in ["esg_strict", "esg_extended"]:
    log.info(f"{col} (units): {st(u[col]).value_counts().to_dict()} | goal-row weighted: "
             f"{u.groupby(st(u[col])).n_goal_rows.sum().to_dict()}")
log.info("method x strict (rows):\n" + pd.crosstab(u.classification_method, st(u.esg_strict), values=u.n_goal_rows, aggfunc="sum").fillna(0).astype(int).to_string())
log.info(f"rules: {len(esg_rules.R)}; version {CLASSIFIER_VERSION}")
