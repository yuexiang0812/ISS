"""Step 05 — Dictionary deliverables (b) and (c).

(b1) Dictionaries/b_revised_rules_v1.0.csv            every rule of classifier v1.0 (regex, kind, pillar, tier, rationale, paper keywords)
(b2) Dictionaries/b_paper_keyword_review_v1.0.csv     data-driven review of ALL 953 AGHJ keywords: occurrences 1998-2021,
                                                      ISS post-2018 diagnostic share, treatment under v1.0, decision
(b3) Dictionaries/b_new_expressions_v1.0.csv          ESG expressions found by v1.0 that no AGHJ keyword matches
(c)  Dictionaries/c_change_log.csv                    versioned log of every keyword / rule change vs. the AGHJ baseline
Files with raw ISS example texts go to Dictionaries/local/ (git-ignored: ISS licence).
"""
import re
import numpy as np, pandas as pd
from config import INTER, DICT, CLASSIFIER_VERSION, get_logger
from classify import COMPILED, classify_unit, scan
from textmatch import kw_regex
import esg_rules

log = get_logger("05_dictionary_deliverables")
LOCAL = DICT / "local"; LOCAL.mkdir(exist_ok=True)
V = CLASSIFIER_VERSION
u = pd.read_parquet(INTER / "text_units_classified.parquet")
g = pd.read_parquet(INTER / "goal_records.parquet", columns=["text_id", "fiscalYear", "iss_esg_flag"])

# ---------------- (b1) rules
TIER = {"ESG": "strict", "EXT": "extended_only", "EXT_AMB": "extended_unknown", "AMB": "strict_unknown",
        "ADJ": "excluded_adjacent", "NONESG": "non_esg", "NONSPEC": "unknown_nonspecific", "MASK": "mask", "MASKN": "mask_non_esg", "FILLER": "filler"}
rules = pd.DataFrame([dict(rule_id=rid, order=i + 1, kind=k, tier=TIER[k], topic=t, pillar=p, confidence=c, regex=pat.pattern,
                           rationale=esg_rules.R[i]["rationale"], derived_from_paper_keywords=esg_rules.R[i]["paper_keywords"])
                      for i, (rid, k, t, p, c, pat) in enumerate(COMPILED)])
hits = u[["text_id", "rule_ids", "n_goal_rows"]].assign(rule=u.rule_ids.str.split("|")).explode("rule")
imp = hits.groupby("rule").agg(n_units=("text_id", "nunique"), n_goal_rows=("n_goal_rows", "sum"))
rules = rules.merge(imp, left_on="rule_id", right_index=True, how="left").fillna({"n_units": 0, "n_goal_rows": 0})
rules["classifier_version"] = V
rules.to_csv(DICT / f"b_revised_rules_{V}.csv", index=False)
log.info(f"(b1) {len(rules)} rules written")

# ---------------- (b2) paper keyword review
kd = pd.read_csv(DICT / "a_paper_dictionary_AGHJ2025_953.csv")
ex = u[u.paper_terms != ""][["text_id", "metricOther_norm", "paper_terms", "esg_strict", "esg_extended", "n_goal_rows"]]
ex = ex.assign(kw=ex.paper_terms.str.split("|")).explode("kw")
yr = g.merge(ex[["text_id", "kw"]], on="text_id")
rows, examples = [], []
for kw in kd.keyword:
    d = ex[ex.kw == kw]; y = yr[yr.kw == kw]
    alone = classify_unit("Other", kw.lower())
    n = d.n_goal_rows.sum()
    sh = lambda v: float((d.n_goal_rows * (d.esg_strict.fillna(-1) == v)).sum() / n) if n else np.nan
    rec = dict(keyword=kw, n_texts=len(d), n_goal_rows=int(n), n_rows_1998_2017=int((y.fiscalYear < 2018).sum()),
               n_rows_2018_2021=int((y.fiscalYear >= 2018).sum()),
               iss_esg_share_2018_2021_diagnostic=round(y[y.fiscalYear >= 2018].iss_esg_flag.mean(), 3) if (y.fiscalYear >= 2018).any() else np.nan,
               v1_share_rows_strict1=round(sh(1), 3), v1_share_rows_strict0=round(sh(0), 3), v1_share_rows_unknown=round(sh(-1), 3),
               v1_keyword_alone_strict=alone["esg_strict"], v1_keyword_alone_extended=alone["esg_extended"],
               v1_keyword_alone_rules=alone["rule_ids"])
    a_s, a_x = alone["esg_strict"], alone["esg_extended"]
    if n == 0:
        dec = "no_occurrence_1998_2021" + ("; covered_by_v1_rule" if a_s == 1 else "; not_carried_forward_or_untested")
    elif a_s == 1 and (rec["v1_share_rows_strict1"] or 0) >= 0.9:
        dec = "retained_strict"
    elif a_s == 1:
        dec = "retained_strict_with_context_exclusions"
    elif a_s is None:
        s1, s0 = rec["v1_share_rows_strict1"], rec["v1_share_rows_strict0"]
        dec = "context_required_keyword_alone_insufficient; " + ("mostly_strict_in_context" if s1 >= 0.6 else "mostly_non_esg_in_context" if s0 >= 0.6 else "mixed_in_context")
    elif a_x == 1:
        dec = "reassigned_extended_only"
    elif "J_" in alone["rule_ids"]:
        dec = "excluded_esg_adjacent_by_definition"
    else:
        dec = "excluded_generic_or_false_positive"
    rec["decision_v1"] = dec
    rows.append(rec)
    fp = d[d.esg_strict == 0].sort_values("n_goal_rows", ascending=False).head(5)
    examples += [dict(keyword=kw, example_metricother=t, v1_strict=0, n_goal_rows=r) for t, r in zip(fp.metricOther_norm, fp.n_goal_rows)]
kr = kd[["kw_id", "keyword", "source_page"]].merge(pd.DataFrame(rows), on="keyword")
kr["classifier_version"] = V
kr.to_csv(DICT / f"b_paper_keyword_review_{V}.csv", index=False)
pd.DataFrame(examples).to_csv(LOCAL / f"b_paper_keyword_false_positive_examples_{V}.csv", index=False)
log.info("(b2) decisions:\n" + kr.decision_v1.value_counts().to_string())

# ---------------- (b3) new expressions (v1 Strict ESG units that no paper keyword matches)
new = u[(u.esg_strict == 1) & (u.paper_terms == "")]
spans = []
for t, n in zip(new.metricOther_norm, new.n_goal_rows):
    for rid, kind, topic, pillar, conf, m in scan(t.lower()):
        if kind == "ESG":
            spans.append(dict(expression=m.lower(), rule_id=rid, topic=topic, pillar=pillar, n_goal_rows=n))
ne = (pd.DataFrame(spans).groupby(["expression", "rule_id", "topic", "pillar"]).agg(n_units=("n_goal_rows", "size"), n_goal_rows=("n_goal_rows", "sum"))
        .reset_index().sort_values("n_goal_rows", ascending=False))
ne.to_csv(DICT / f"b_new_expressions_{V}.csv", index=False)
log.info(f"(b3) {len(ne)} new expressions; {len(new)} units / {new.n_goal_rows.sum()} goal rows ESG under v1 but unmatched by AGHJ")

# ---------------- (c) change log
C = [
 ("v0", "baseline", "", "AGHJ (2025) Appendix A.3, 953 keywords, literal case-insensitive whole-token match on metricOther", "Dictionaries/a_paper_dictionary_AGHJ2025_953.csv"),
 (V, "design", "all", "Three-state labels (1/0/Unknown); 0 requires positive non-ESG evidence; Unknown for placeholders and unmatched text", "task brief s.5"),
 (V, "design", "all", "metric and metricOther read jointly; only time-consistent metric labels used; 2018-taxonomy ESG labels and ISS metricType ESG categories never used as evidence", "Logs/03_goal_extraction.log (label first-year table)"),
 (V, "design", "C01", "Blank metric+metricOther: time-consistent financial metricType (Accounting / Stock Price = Market-related ...) admitted as structured context -> 0; text-only label kept Unknown", "ISS User Guide p.12"),
 (V, "design", "R*", "Rules consume matched spans in priority order (masks -> routed phrases -> strict -> extended -> ambiguous -> adjacent -> placeholders -> non-ESG)", "Code/classify.py"),
 (V, "exclusion", "fp_*", "Masks for false positives found in data: safety and soundness, clinical safety data, accident-year, cost/debt reduction (no longer a keyword), capital recycling, minority investment, business 'environment', financial 'sustainable', company/segment names (Peoples Gas, Hess, Clean Energy Businesses, Sam's Club, Workday, NOV), real-estate 'communities', AML leukaemia, PV, 'inclusive of', audience/viewers, 'partly offset'", "b_paper_keyword_review (excluded_* rows); local FP examples"),
 (V, "reassign", "X_*", "Customer satisfaction/experience/retention, product/patient/food safety, healthcare quality, privacy/fair lending, utility service reliability (SAIDI/SAIFI), community engagement -> Extended-only (task brief 4.4)", "b_revised_rules"),
 (V, "exclusion", "J_compliance_risk", "Generic compliance, regulatory exams, risk management, internal controls, SOX, audit, cybersecurity, AML/BSA -> 0/0 flagged ESG-adjacent (task brief 4.3)", ""),
 (V, "exclusion", "J_workforce_generic", "Talent management, succession planning, leadership development, culture, HR, hiring, teamwork -> 0/0 flagged (task brief 4.2); specific engagement/retention/turnover/training/wellbeing stay Strict S", ""),
 (V, "exclusion", "J_renewable_business", "Wind/solar project execution, renewable portfolio growth/availability -> 0/0 flagged (business-line economic meaning); renewable energy adoption/share/carbon-free capacity stays Strict E", ""),
 (V, "ambiguity", "A_*", "Energy efficiency / DSM (cost vs environment), bare water/waste/green/clean/renewables, notices of violation without environmental context, bare integrity/social/turnover -> Strict Unknown", "task brief 4.1"),
 (V, "addition", "S_ohs", "Added safety expressions absent from AGHJ: EH&S, HS&E, H&S, near miss (no hyphen), days away restricted (variants), life-changing events, medical aid, serious incidents", "b_new_expressions"),
 (V, "addition", "E_*", "Added: flaring/flare volumes, reportable/significant/off-property releases, scrubbers, reclamation, leak detection, particulate", "b_new_expressions"),
 (V, "addition", "S_dei/S_human_capital/G_ethics", "Added: D&I, DE&I, ethical conduct, associate satisfaction/experience/development, corporate well-being, retain talent, staff/teller/labor turnover, board evaluation", "b_new_expressions"),
 (V, "pillar", "GEN_*", "ESG/CSR/citizenship/sustainability not forced into E/S/G: pillar flags Unknown unless a specific pillar term co-occurs ('sustainability' then treated as qualifier)", ""),
 (V, "freeze", "all", "Rules frozen before drawing the independent validation sample (Validation/validation_sample_v1.0.csv)", ""),
]
pd.DataFrame(C, columns=["version", "change_type", "rule_or_scope", "description", "evidence_or_file"]).to_csv(DICT / "c_change_log.csv", index=False)
log.info("(c) change log written")
