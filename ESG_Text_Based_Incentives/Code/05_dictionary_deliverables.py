"""Step 05 — Dictionary deliverables (b) and (c).

中文说明：生成词典交付物——(b1) 全部规则（含中文主题说明、版本变更标注）；(b2) 论文 953 个关键词逐个审查结论；
(b3) 论文词典未覆盖的新 ESG 表达；(b4) 每条规则实际匹配到的典型短语；(c) 版本修改记录（v1.0 与 v1.1 分开记录）。
文件名中的版本号随 CLASSIFIER_VERSION 变化，旧版本文件保留以便对照。

(b1) Dictionaries/b_revised_rules_<v>.csv            every rule (regex, kind, pillar, tier, rationale, paper keywords, version change note)
(b2) Dictionaries/b_paper_keyword_review_<v>.csv     data-driven review of ALL 953 AGHJ keywords: occurrences 1998-2021,
                                                     ISS post-2018 diagnostic share, treatment under the current version, decision
(b3) Dictionaries/b_new_expressions_<v>.csv          ESG expressions found by the current version that no AGHJ keyword matches
(b4) Dictionaries/b_rule_match_examples_<v>.csv      most frequent matched phrases per rule (what each rule actually captures)
(c)  Dictionaries/c_change_log.csv                   versioned log of every keyword / rule change vs. the AGHJ baseline
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
TOPIC_CN = {
    "S_ohs": "职业/工艺/运营健康与安全", "S_public_safety": "公共安全（管线、燃气泄漏、山火等）", "S_dei": "多元、公平与包容",
    "S_human_capital": "具体的人力资本目标（敬业度、留任、培训、福祉）", "S_community": "社区投资、志愿、慈善", "S_access_inclusion": "明确定义的社会普惠目标",
    "S_human_rights": "人权、劳工标准、负责任采购", "E_ghg_air": "温室气体与大气排放", "E_climate": "气候目标与政策", "E_energy_transition": "可再生能源采用与节能",
    "E_water": "水资源", "E_waste": "废弃物与回收", "E_releases": "泄漏与环境排放事件", "E_env_general": "明确的环境绩效",
    "G_ethics": "商业道德与反腐", "G_governance": "具体的公司治理目标", "GEN_esg": "ESG/CSR 综合（维度未指明）", "GEN_sustainability": "可持续发展（综合）",
    "X_customer": "客户/患者满意度、体验、留存", "X_quality_care": "医疗服务质量", "X_product_resp": "产品责任、隐私、公平对待客户",
    "X_product_safety": "产品/食品/患者安全", "X_patient_safety": "患者安全结果", "X_service_reliability": "面向客户的供电可靠性",
    "X_community_engagement": "社区与利益相关方关系", "X_quality_generic": "笼统的“质量/可靠性”（Extended 未知）",
    "A_energy_efficiency": "能效（成本还是环境目标不明）", "A_environment_bare": "单独的环境词（水、废物、绿色等）", "A_social_bare": "单独的社会词",
    "A_governance_bare": "单独的“治理”（内容不具体）", "J_compliance_risk": "一般性合规/风险/内控/网络安全（排除）", "J_workforce_generic": "一般性人才/继任/文化/劳资谈判（排除）",
    "J_renewable_business": "可再生能源业务线执行（排除）", "J_esg_business_line": "ESG 产品/业务线（排除）", "J_public_affairs": "游说与公共事务（排除）",
    "U_nonspecific": "未披露内容的占位描述（未知）", "N_financial": "财务指标", "N_operating": "经营/研发/业务计划指标", "F_filler": "无信息的通用词"}
rules = pd.DataFrame([dict(rule_id=rid, order=i + 1, kind=k, tier=TIER[k], topic=t, topic_cn=TOPIC_CN.get(t, "屏蔽规则（排除误报短语）" if k.startswith("MASK") else ""),
                           pillar=p, confidence=c, regex=pat.pattern, rationale=esg_rules.R[i]["rationale"],
                           derived_from_paper_keywords=esg_rules.R[i]["paper_keywords"], version_change=esg_rules.R[i].get("changed", ""))
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
               share_rows_strict1=round(sh(1), 3), share_rows_strict0=round(sh(0), 3), share_rows_unknown=round(sh(-1), 3),
               keyword_alone_strict=alone["esg_strict"], keyword_alone_extended=alone["esg_extended"],
               keyword_alone_rules=alone["rule_ids"])
    a_s, a_x = alone["esg_strict"], alone["esg_extended"]
    if n == 0:
        dec = "no_occurrence_1998_2021" + ("; covered_by_v1_rule" if a_s == 1 else "; not_carried_forward_or_untested")
    elif a_s == 1 and (rec["share_rows_strict1"] or 0) >= 0.9:
        dec = "retained_strict"
    elif a_s == 1:
        dec = "retained_strict_with_context_exclusions"
    elif a_s is None:
        s1, s0 = rec["share_rows_strict1"], rec["share_rows_strict0"]
        dec = "context_required_keyword_alone_insufficient; " + ("mostly_strict_in_context" if s1 >= 0.6 else "mostly_non_esg_in_context" if s0 >= 0.6 else "mixed_in_context")
    elif a_x == 1:
        dec = "reassigned_extended_only"
    elif "J_" in alone["rule_ids"]:
        dec = "excluded_esg_adjacent_by_definition"
    else:
        dec = "excluded_generic_or_false_positive"
    rec["decision"] = dec
    rows.append(rec)
    fp = d[d.esg_strict == 0].sort_values("n_goal_rows", ascending=False).head(5)
    examples += [dict(keyword=kw, example_metricother=t, strict=0, n_goal_rows=r) for t, r in zip(fp.metricOther_norm, fp.n_goal_rows)]
kr = kd[["kw_id", "keyword", "source_page"]].merge(pd.DataFrame(rows), on="keyword")
kr["classifier_version"] = V
kr.to_csv(DICT / f"b_paper_keyword_review_{V}.csv", index=False)
pd.DataFrame(examples).to_csv(LOCAL / f"b_paper_keyword_false_positive_examples_{V}.csv", index=False)
log.info("(b2) decisions:\n" + kr.decision.value_counts().to_string())

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
log.info(f"(b3) {len(ne)} new expressions; {len(new)} units / {new.n_goal_rows.sum()} goal rows ESG under {V} but unmatched by AGHJ")

# ---------------- (b4) what each rule actually captures (top matched phrases, weighted by goal rows)
sp = []
for t, n in zip(u.metricOther_norm, u.n_goal_rows):
    if t:
        for rid, kind, topic, pillar, conf, m in scan(t.lower()):
            if kind != "FILLER":
                sp.append((rid, m.lower(), n))
sp = pd.DataFrame(sp, columns=["rule_id", "matched_phrase", "n_goal_rows"]).groupby(["rule_id", "matched_phrase"]).n_goal_rows.sum().reset_index()
sp = sp.sort_values(["rule_id", "n_goal_rows"], ascending=[True, False]).groupby("rule_id").head(15)
sp.to_csv(DICT / f"b_rule_match_examples_{V}.csv", index=False)
log.info(f"(b4) rule match examples: {len(sp)} rows")

# ---------------- (c) change log
C = [
 ("v0", "baseline", "", "AGHJ (2025) Appendix A.3, 953 keywords, literal case-insensitive whole-token match on metricOther", "Dictionaries/a_paper_dictionary_AGHJ2025_953.csv"),
 ("v1.0", "design", "all", "Three-state labels (1/0/Unknown); 0 requires positive non-ESG evidence; Unknown for placeholders and unmatched text", "task brief s.5"),
 ("v1.0", "design", "all", "metric and metricOther read jointly; only time-consistent metric labels used; 2018-taxonomy ESG labels and ISS metricType ESG categories never used as evidence", "Logs/03_goal_extraction.log (label first-year table)"),
 ("v1.0", "design", "C01", "Blank metric+metricOther: time-consistent financial metricType (Accounting / Stock Price = Market-related ...) admitted as structured context -> 0; text-only label kept Unknown", "ISS User Guide p.12"),
 ("v1.0", "design", "R*", "Rules consume matched spans in priority order (masks -> routed phrases -> strict -> extended -> ambiguous -> adjacent -> placeholders -> non-ESG)", "Code/classify.py"),
 ("v1.0", "exclusion", "fp_*", "Masks for false positives found in data: safety and soundness, clinical safety data, accident-year, cost/debt reduction (no longer a keyword), capital recycling, minority investment, business 'environment', financial 'sustainable', company/segment names (Peoples Gas, Hess, Clean Energy Businesses, Sam's Club, Workday, NOV), real-estate 'communities', AML leukaemia, PV, 'inclusive of', audience/viewers, 'partly offset'", "b_paper_keyword_review (excluded_* rows); local FP examples"),
 ("v1.0", "reassign", "X_*", "Customer satisfaction/experience/retention, product/patient/food safety, healthcare quality, privacy/fair lending, utility service reliability (SAIDI/SAIFI), community engagement -> Extended-only (task brief 4.4)", "b_revised_rules"),
 ("v1.0", "exclusion", "J_compliance_risk", "Generic compliance, regulatory exams, risk management, internal controls, SOX, audit, cybersecurity, AML/BSA -> 0/0 flagged ESG-adjacent (task brief 4.3)", ""),
 ("v1.0", "exclusion", "J_workforce_generic", "Talent management, succession planning, leadership development, culture, HR, hiring, teamwork -> 0/0 flagged (task brief 4.2); specific engagement/retention/turnover/training/wellbeing stay Strict S", ""),
 ("v1.0", "exclusion", "J_renewable_business", "Wind/solar project execution, renewable portfolio growth/availability -> 0/0 flagged (business-line economic meaning); renewable energy adoption/share/carbon-free capacity stays Strict E", ""),
 ("v1.0", "ambiguity", "A_*", "Energy efficiency / DSM (cost vs environment), bare water/waste/green/clean/renewables, notices of violation without environmental context, bare integrity/social/turnover -> Strict Unknown", "task brief 4.1"),
 ("v1.0", "addition", "S_ohs", "Added safety expressions absent from AGHJ: EH&S, HS&E, H&S, near miss (no hyphen), days away restricted (variants), life-changing events, medical aid, serious incidents", "b_new_expressions"),
 ("v1.0", "addition", "E_*", "Added: flaring/flare volumes, reportable/significant/off-property releases, scrubbers, reclamation, leak detection, particulate", "b_new_expressions"),
 ("v1.0", "addition", "S_dei/S_human_capital/G_ethics", "Added: D&I, DE&I, ethical conduct, associate satisfaction/experience/development, corporate well-being, retain talent, staff/teller/labor turnover, board evaluation", "b_new_expressions"),
 ("v1.0", "pillar", "GEN_*", "ESG/CSR/citizenship/sustainability not forced into E/S/G: pillar flags Unknown unless a specific pillar term co-occurs ('sustainability' then treated as qualifier)", ""),
 ("v1.0", "freeze", "all", "Rules frozen before drawing the independent validation sample (Validation/validation_sample_v1.0_KEY_local.csv)", ""),
 ("v1.1", "review", "all", "Full re-review of v1.0 on the data: every suspicious pattern tested on real texts; findings in Documentation/review_findings_v1.1.csv", "Documentation/review_findings_v1.1.csv"),
 ("v1.1", "definition", "G_governance / A_governance_bare", "Bare 'governance' no longer Strict G (task brief 4.3 requires specific governance content); now Strict Unknown. Strict G = corporate governance, board, shareholder rights, say-on-pay, governance ratings", "b_revised_rules_v1.1.csv"),
 ("v1.1", "exclusion", "J_esg_business_line", "ESG products / segment sales / ESG AUM are business lines -> 0/0 flagged (were Strict GEN)", ""),
 ("v1.1", "exclusion", "J_public_affairs", "Government relations / lobbying / legislative advocacy -> 0/0 flagged (government relations was Extended)", ""),
 ("v1.1", "reassign", "X_customer route", "Customer/patient/member engagement routed to Extended before the employee-engagement rule ('Customer Engagement Index' was Strict S)", ""),
 ("v1.1", "fix", "S_human_capital", "'partner' removed as an employee noun; retention recognised at a distance ('retention and development of high-potential employees'); word boundary on 'mental health'", ""),
 ("v1.1", "addition", "S_ohs", "Worker radiation exposure (collective dose, RFO dose), loss of containment / process fluid containment, LCE acronym; protected 'safe/healthy work environment'", ""),
 ("v1.1", "addition", "S_access_inclusion / S_dei / S_human_rights / E_waste / X_quality_care", "Community Reinvestment Act, health equity, animal welfare / cage-free, coal ash, Medicare STARS", ""),
 ("v1.1", "fix", "masks", "+ 'satisfaction of' (fulfilment), insurance 'individual' product lines, discretionary cash flow/spend, social media, community count (now non-ESG evidence), segment names (corrugated and recycling, user-experience segment, environmental-services segment), 'diverse' word boundary (Diversey)", ""),
 ("v1.1", "fix", "N_financial / N_operating", "Non-ESG vocabulary extended (balance sheet, CASM/RASM, dayrates, LIFO, rating agencies, diversification, mining volumes, active users, clinical-dose milestones ...) -> fewer spurious Unknowns", ""),
 ("v1.1", "fix", "pillars", "A pillar-specific ambiguous hit leaves that pillar Unknown when the text is Strict ESG via another pillar (e.g. 'Safety and Governance' -> G Unknown, not 0)", "Code/classify.py"),
 ("v1.1", "fix", "esg_extended_only", "Extended-only is Unknown (not 1) when Strict is Unknown and Extended is 1", "Code/classify.py"),
 ("v1.1", "id", "text_id", "text_id = 'T' + first 10 hex of SHA-1(text_key): stable across versions; human labels join on text_key / sample_id", "Code/04_text_classification.py"),
]
pd.DataFrame(C, columns=["version", "change_type", "rule_or_scope", "description", "evidence_or_file"]).to_csv(DICT / "c_change_log.csv", index=False)
log.info("(c) change log written")
