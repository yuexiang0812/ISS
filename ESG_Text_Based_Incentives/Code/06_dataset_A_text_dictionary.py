"""Step 06 — Dataset A: ESG_Text_Dictionary.dta (one row per classification unit).

中文说明：生成文本分类字典（数据集 A）。若存在裁定后的人工标注（Validation/human_labels/adjudicated_labels.csv），
人工标签覆盖模型标签（状态 confirmed、方法 human_review、human_reviewed=1）；模型原始标签始终保留在 *_model 列，
用于验证时与人工参考标签对比。人工标注可用 sample_id、text_key 或 text_id 定位，取值 1 / 0 / U（见 humanlabels.py）。

Human review integration: adjudicated human labels override the model labels; the rule-based labels are always kept
in *_model columns so validation can compare them against the human reference.
"""
import numpy as np, pandas as pd
from config import INTER, VALID, CLASSIFIER_VERSION, get_logger
from dtautil import write_dta
from classify import extended_only_vec
from humanlabels import load_adjudicated

log = get_logger("06_dataset_A_text_dictionary")
u = pd.read_parquet(INTER / "text_units_classified.parquet")
for c in ["esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g", "esg_strict_textonly", "esg_extended_textonly"]:
    u[c] = pd.to_numeric(u[c], errors="coerce")
for c in ["esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g", "classification_method", "classification_confidence"]:
    u[c + "_model"] = u[c]
u["human_reviewed"] = 0

h = load_adjudicated(u)
if h is not None:
    h = h[h.text_key.isin(u.text_key)].set_index("text_key")
    m = u.text_key.isin(h.index)
    for c in ["esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g"]:
        u.loc[m, c] = u.loc[m, "text_key"].map(h["human_" + c]).astype(float)
    u.loc[m, "classification_method"] = "human_review"; u.loc[m, "classification_confidence"] = "human"
    u.loc[m, "human_reviewed"] = 1
    log.info(f"human adjudicated labels applied to {int(m.sum())} units; Strict=1=>Extended=1 auto-fixed in "
             f"{int(h.human_invariant_fixed.sum())} human rows")
else:
    log.info("no adjudicated human labels found -> all labels are model/rule-based (provisional)")

# Extended must contain all Strict positives (invariant)
bad = (u.esg_strict == 1) & (u.esg_extended != 1)
log.info(f"invariant check strict=1 => extended=1 violations: {int(bad.sum())}"); assert not bad.any()
u["esg_extended_only"] = extended_only_vec(u.esg_strict, u.esg_extended)
u["classification_status"] = np.select([(u.human_reviewed == 1) & u.esg_strict.notna(), u.human_reviewed == 1, u.esg_strict.isna()],
                                        ["confirmed", "confirmed_unknown", "unknown"], "provisional")
u["text_normalized"] = u.metricOther_norm.str.lower()
u["review_priority"] = np.select(
    [u.esg_strict.isna() & (u.n_goal_rows >= 20), u.review_flags != "", u.classification_confidence.isin(["low", "medium"]) & (u.n_goal_rows >= 20)],
    ["high_unknown_frequent", "flagged_rule_conflict", "medium_confidence_frequent"], "")

cols = ["text_id", "text_key", "text_original", "text_normalized", "metric", "context_used",
        "esg_strict", "esg_extended", "esg_extended_only", "esg_e", "esg_s", "esg_g", "esg_general",
        "esg_strict_textonly", "esg_extended_textonly",
        "classification_status", "classification_method", "classification_confidence", "classification_reason",
        "esg_topics", "adjacent_flags", "review_flags", "review_priority", "rule_ids", "human_reviewed",
        "esg_strict_model", "esg_extended_model", "esg_e_model", "esg_s_model", "esg_g_model", "classification_method_model",
        "paper_esg", "paper_esg_as_used", "paper_terms", "iss_esg_share", "metricType_mode",
        "first_year", "last_year", "n_goal_rows", "n_rows_pre2018", "n_grants", "n_firms", "classifier_version"]
A = u[cols].rename(columns={"metricType_mode": "metrictype_mode", "iss_esg_share": "iss_esg_share_diag",
                            "context_used": "classification_context"})
A.to_parquet(INTER / "dataset_A.parquet", index=False)
L = dict(text_id="Unique text-classification unit identifier", text_key="Standardized key: metric || lower(metricOther) [|| ctx]",
         text_original="Representative original metricOther text", text_normalized="Normalized metricOther (NFKC, whitespace, lower)",
         metric="ISS standardized metric label", classification_context="Structured context used (only blank text): fin_metrictype/no_text/iss_esg_label_only",
         esg_strict="Strict ESG: 1/0/. (.=Unknown)", esg_extended="Extended ESG (Strict + stakeholder): 1/0/.",
         esg_extended_only="Extended-only (stakeholder, not Strict): 1/0/.", esg_e="Environmental (Strict): 1/0/.",
         esg_s="Social (Strict): 1/0/.", esg_g="Governance (Strict): 1/0/.", esg_general="Multi-pillar ESG/CSR/sustainability term present",
         esg_strict_textonly="Strict ESG using text only (no structured context)", esg_extended_textonly="Extended ESG using text only",
         classification_status="confirmed (human) / confirmed_unknown (human: undecidable) / provisional (rule) / unknown", classification_method="deterministic_rule / structured_context / human_review / unresolved",
         classification_confidence="high / medium / low / human", classification_reason="Rules fired with matched text; masks; label notes",
         esg_topics="ESG / stakeholder topics matched", adjacent_flags="ESG-adjacent exclusions matched (J_*)", review_flags="Rule-conflict flags",
         review_priority="Priority for human review queue", rule_ids="Rule ids fired (Dictionaries/b_revised_rules)", human_reviewed="1 if adjudicated human label applied",
         esg_strict_model="Strict ESG from v1 rules (before human override)", esg_extended_model="Extended ESG from v1 rules",
         esg_e_model="E from v1 rules", esg_s_model="S from v1 rules", esg_g_model="G from v1 rules", classification_method_model="Method of v1 rules",
         paper_esg="AGHJ(2025) 953-keyword match on metricOther (. = blank text)", paper_esg_as_used="AGHJ match, blank/no match = 0 (as in paper)",
         paper_terms="AGHJ keywords matched", iss_esg_share_diag="DIAGNOSTIC: share of rows with ISS ESG metricType/label",
         metrictype_mode="Most frequent ISS metricType (diagnostic)", first_year="Earliest fiscal year observed", last_year="Latest fiscal year observed",
         n_goal_rows="Number of raw goal records", n_rows_pre2018="Goal records before 2018", n_grants="Distinct grants containing the text",
         n_firms="Distinct firms (CIK) using the text", classifier_version="Classifier version")
write_dta(A, "ESG_Text_Dictionary.dta", L, log, keys=["text_id"])
log.info("status x strict:\n" + pd.crosstab(A.classification_status, A.esg_strict.fillna(-1)).to_string())
