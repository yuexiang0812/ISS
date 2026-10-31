"""Step 17 — Version comparison (previous version -> current version) and review findings register.

中文说明：把当前版本（CLASSIFIER_VERSION）与上一版本（PREVIOUS_VERSION，快照在 Data/Intermediate/snapshot_<版本>/）逐层比较：
文本单元标签迁移（按单元与目标记录加权）、按规则主题归因的变化、公司-年采用率与占比的年度差异；并输出本次审查的“发现清单”
（每条问题：发现了什么、证据、严重性、如何修正、影响），用于让使用者理解两个版本的区别。含 ISS 原文的变化明细只存本地。

Outputs: Documentation/version_comparison_<prev>_to_<cur>_*.csv, Documentation/review_findings_<cur>.csv,
         Validation/version_changed_units_<prev>_to_<cur>_local.csv
"""
import numpy as np, pandas as pd
from config import INTER, DOCS, VALID, CLASSIFIER_VERSION, PREVIOUS_VERSION, get_logger

log = get_logger("17_version_comparison")
V, P = CLASSIFIER_VERSION, PREVIOUS_VERSION
SNAP = INTER / f"snapshot_{P}"
tag = f"{P}_to_{V}"
lab = lambda s: s.map({1.0: "1", 0.0: "0"}).fillna("U")

if not SNAP.exists():
    log.info(f"no snapshot of {P}: comparison skipped")
    raise SystemExit(0)

# ---------------- unit-level label transitions
A0 = pd.read_parquet(SNAP / "dataset_A.parquet")
A1 = pd.read_parquet(INTER / "dataset_A.parquet")
J = A1[["text_key", "text_original", "metric", "n_goal_rows", "first_year", "last_year", "esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g",
        "esg_topics", "adjacent_flags", "classification_reason"]].merge(
    A0[["text_key", "esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g", "esg_topics"]], on="text_key", how="outer", suffixes=("", "_prev"), indicator=True)
log.info(f"unit sets: {J._merge.value_counts().to_dict()} (units are defined by data + normalisation, not by rules)")
rows = []
for d in ["esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g"]:
    t = pd.crosstab(lab(J[d + "_prev"]), lab(J[d]), values=J.n_goal_rows, aggfunc="sum").fillna(0).astype(int)
    tu = pd.crosstab(lab(J[d + "_prev"]), lab(J[d]))
    for a in tu.index:
        for b in tu.columns:
            rows.append(dict(dimension=d, label_prev=a, label_current=b, units=int(tu.loc[a, b]), goal_rows=int(t.loc[a, b]) if a in t.index and b in t.columns else 0))
TR = pd.DataFrame(rows)
TR.to_csv(DOCS / f"version_comparison_{tag}_label_transitions.csv", index=False)
log.info("Strict label transitions (goal rows):\n" + TR[TR.dimension == "esg_strict"].pivot_table(index="label_prev", columns="label_current", values="goal_rows").to_string())

ch = J[(lab(J.esg_strict) != lab(J.esg_strict_prev)) | (lab(J.esg_extended) != lab(J.esg_extended_prev)) |
       (lab(J.esg_e) != lab(J.esg_e_prev)) | (lab(J.esg_s) != lab(J.esg_s_prev)) | (lab(J.esg_g) != lab(J.esg_g_prev))].copy()
ch["change"] = ("strict " + lab(ch.esg_strict_prev) + "->" + lab(ch.esg_strict) + "; ext " + lab(ch.esg_extended_prev) + "->" + lab(ch.esg_extended)
                + "; E/S/G " + lab(ch.esg_e_prev) + lab(ch.esg_s_prev) + lab(ch.esg_g_prev) + "->" + lab(ch.esg_e) + lab(ch.esg_s) + lab(ch.esg_g))
ch.sort_values("n_goal_rows", ascending=False).to_csv(VALID / f"version_changed_units_{tag}_local.csv", index=False)
ct = ch.groupby("change").agg(units=("text_key", "size"), goal_rows=("n_goal_rows", "sum")).sort_values("goal_rows", ascending=False)
ct.to_csv(DOCS / f"version_comparison_{tag}_change_types.csv")
log.info(f"units whose labels changed: {len(ch):,} ({ch.n_goal_rows.sum():,} goal rows)\n" + ct.head(25).to_string())

# ---------------- firm-year and executive-year annual comparison
def annual(F):
    d = F[F.firm_n_perf_grants > 0]
    return d.groupby("fiscalyear").agg(firms=("cik", "size"),
                                      adopt_lb=("firm_perf_esg_adopt_strict", lambda s: (s == 1).mean()),
                                      adopt_ub=("firm_perf_esg_adopt_strict", lambda s: (s != 0).mean()),
                                      adopt_ext_lb=("firm_perf_esg_adopt_extended", lambda s: (s == 1).mean()),
                                      e_lb=("firm_esg_e_adopt", lambda s: (s == 1).mean()), s_lb=("firm_esg_s_adopt", lambda s: (s == 1).mean()),
                                      g_lb=("firm_esg_g_adopt", lambda s: (s == 1).mean()),
                                      perf_share_lb=("firm_esg_perf_share_lb", "mean"), value_share=("firm_perf_esg_compensation_value_share", "mean"))
F0 = annual(pd.read_parquet(SNAP / "dataset_F.parquet")); F1 = annual(pd.read_parquet(INTER / "dataset_F.parquet"))
AC = F0.add_suffix(f"_{P}").join(F1.add_suffix(f"_{V}"))
for c in ["adopt_lb", "adopt_ub", "adopt_ext_lb", "e_lb", "s_lb", "g_lb", "perf_share_lb", "value_share"]:
    AC[f"diff_{c}"] = AC[f"{c}_{V}"] - AC[f"{c}_{P}"]
AC.round(4).to_csv(DOCS / f"version_comparison_{tag}_firm_annual.csv")
log.info("firm-year Strict adoption lb / ub by version (selected years):\n" +
         AC.loc[[y for y in (1998, 2008, 2015, 2016, 2017, 2018, 2019, 2020, 2021) if y in AC.index],
                [f"adopt_lb_{P}", f"adopt_lb_{V}", f"adopt_ub_{P}", f"adopt_ub_{V}", f"g_lb_{P}", f"g_lb_{V}", f"value_share_{P}", f"value_share_{V}"]].round(3).to_string())

# ---------------- review findings register (what was found in the v1.1 review, why it mattered, how it was fixed)
n = lambda cond: (int(cond.sum()), int(J.loc[cond, "n_goal_rows"].sum()))
gb = n((J.esg_g_prev == 1) & (J.esg_g != 1))
fmt = lambda t: f"{t[0]} units / {t[1]} goal rows"
r02 = n(J.adjacent_flags.fillna("").str.contains("J_esg_business_line"))
r03 = n((J.esg_strict_prev == 1) & (J.esg_strict == 0) & J.esg_topics.fillna("").str.contains("X_customer"))
r04 = n(J.esg_strict_prev.isna() & (J.esg_strict == 1))
r05 = n(J.esg_strict_prev.isna() & (J.esg_strict == 0))
r06 = n(J.text_original.fillna("").str.lower().str.contains("satisfaction of") & (J.esg_extended_prev == 1) & (J.esg_extended != 1))
r07 = n(J.text_original.fillna("").str.lower().str.contains("community reinvestment"))
r08 = n(J.adjacent_flags.fillna("").str.contains("J_public_affairs") & (J.esg_extended_prev == 1))
F_ = [
 ("R01", "classification", "high", "Bare 'governance' was Strict G, contrary to task brief 4.3 (governance must be specific)",
  f"{gb[0]} units / {gb[1]} goal rows lose G=1 in {V}", "Strict G only for corporate governance, board, shareholder rights, say-on-pay, governance ratings; bare 'governance' -> Unknown (A_governance_bare)"),
 ("R02", "classification", "medium", "ESG business lines (MSCI 'ESG segments net new sales', 'ESG-Dedicated AUM') were Strict ESG", fmt(r02), "J_esg_business_line -> 0/0 flagged"),
 ("R03", "classification", "medium", "'Customer Engagement Index' was Strict S via the employee 'engagement index' rule; 'Customer/Partner Engagement' was Strict S", fmt(r03), "customer/patient/member engagement routed to Extended first; 'partner' removed from employee nouns"),
 ("R04", "classification", "medium", "Worker radiation dose (nuclear), loss of containment, 'LCEs', 'Retention ... of high potential employees', 'Employee one-year retention' were Unknown (false negatives)", fmt(r04) + " move Unknown -> Strict 1 in total (all new rules)", "rules added (S_ohs, S_human_capital, S_access_inclusion ...)"),
 ("R05", "classification", "medium", "Spurious Unknowns: discretionary cash flow, insurance 'Individual Markets/Life' lines, strategic diversification, balance sheet, CASM/RASM, dayrates, clinical dose milestones, community count", fmt(r05) + " move Unknown -> 0", "non-ESG vocabulary and masks extended"),
 ("R06", "classification", "low", "'Satisfaction of strategic sales goals' (fulfilment) was Extended (customer satisfaction)", fmt(r06), "mask 'satisfaction of'"),
 ("R07", "classification", "low", "Community Reinvestment Act results were only Extended", fmt(r07), "S_access_inclusion (Strict S)"),
 ("R08", "classification", "low", "Government relations were Extended (stakeholder); lobbying is not an ESG performance outcome", fmt(r08), "J_public_affairs -> 0/0 flagged"),
 ("R09", "classification", "low", "'mental health' lacked a word boundary (matched inside 'environmental health'); 'diverse' lacked one (Diversey)", "no label changed in data", "word boundaries added"),
 ("R10", "logic", "medium", "Pillar label set to 0 although an ambiguous word for that pillar was present (e.g. 'Safety and Governance' -> G=0)", "pillars", "pillar-specific ambiguous hit leaves the pillar Unknown"),
 ("R11", "logic", "medium", "esg_extended_only = 1 when Strict was Unknown and Extended = 1 (should be Unknown)", "22 units / 103 goal rows in v1.0", "extended_only() helper used everywhere"),
 ("R12", "logic", "high", "E/S/G adoption required ALL performance grants to be non-ESG for a 0; a firm with only S conditions got E = Unknown instead of 0", "pillar adoption at every level", "pillar adoption = 0 when every performance grant has pillar = 0"),
 ("R13", "logic", "medium", "E/S/G grant and KPI shares were published as exact although they are lower bounds (general ESG terms leave pillars unresolved)", "all pillar shares", "exact only when every pillar label is known, plus _lb/_ub"),
 ("R14", "data", "medium", "144 duplicated grantIDs had conflicting performancetype ('Abs' and 'Time'; 3 also 'Rel'); v1.0 kept the first row by accident", "141 grants with goal data", "type resolved from goal data (Abs/Rel/AbsRel), flagged grant_dup_resolved"),
 ("R15", "data", "medium", "Grants whose declared number of objectives exceeds recorded objectives were classified 0 although the missing objectives could be ESG", "362 grants (16 previously 0)", "grant_goal_data_incomplete flag; ESG Unknown unless an ESG KPI is present"),
 ("R16", "measure", "high", "Value share used grant-date fair value only, which is missing for 98.6% of cash-incentive awards (ISS stores their target payout in nonEquityTarget); ESG sits mostly in annual cash plans, so exposure was understated", "all value-share variables", "grant_value_combined = fair value, else non-equity target payout; value_source flagged"),
 ("R17", "measure", "low", "Counts were missing (not 0) for CEOs and firm-years without grants", "2,459 CEO rows; 776 firm-years", "fill_counts(): counts 0, measures stay missing"),
 ("R18", "analysis", "medium", "Balanced panel selected firms whose adoption was KNOWN every year (selection on the outcome; 40% adoption)", "annual analysis", "balanced panel = firms with performance grants every year 2015-2021; lb/cc/ub reported"),
 ("R19", "validation", "high", "Scoring code had never been executed: 'U' labels broke numeric comparisons, joins used version-specific text_id, bootstrap ignored strata, kappa mishandled missing", "validation step", "humanlabels.py (1/0/U parsing, sample_id/text_key joins), stratified bootstrap, kappa with Unknown category; tested on synthetic labels"),
 ("R20", "reproducibility", "medium", "text_id was a sequence number (changes when units change); the frozen sample existed only in a local file with ISS text", "ids / sample", "text_id = SHA-1 hash of text_key; pushable id list validation_sample_v1.0_ids.csv"),
 ("R21", "documentation", "medium", "Methodology report numbers were hand-typed (would go stale after any data update); several variable definitions were blank", "docs", "report generated from current outputs (Step 18); every variable defined (Step 15)"),
 ("R22", "transparency", "low", "No independent check of the AGHJ implementation", "", "approximate replication of AGHJ Table 1 (Validation/e_paper_replication_benchmark.csv)"),
 ("R23", "data", "high", "Stata export forced latin-1 and replaced non-latin-1 characters (e.g. ’ —) with '?' in every string variable (found by the v1.1 audit: text_id hash check failed)",
  "418 text units had altered text in the v1.0 .dta files", "write UTF-8 (Stata 118 native); audit verifies text_key round-trips exactly (hash check)"),
 ("R24", "development check", "high", "Caught BEFORE release: in the rewritten aggregation the helper count for pillar S shared a name with the Strict count, so S adoption equalled Strict adoption",
  "found by inspecting v1.1 outputs (S adoption = Strict adoption in every year)", "distinct helper names + assertion against duplicates; audit re-derives E, S and G adoption and shares from grants and guards S != Strict"),
 ("R25", "development check", "medium", "Caught BEFORE release by reviewing every changed unit: 'work environment' fell to the Environmental rule; 'placement' matched inside 'replacement'; specific board-governance phrases became Unknown",
  "about 10 units", "'work environment' -> Social; word boundaries; board-governance phrasing rule"),
]
RF = pd.DataFrame(F_, columns=["finding_id", "area", "severity", "finding", "evidence_or_impact", "fix_in_" + V])
RF["status"] = "fixed in " + V
RF.to_csv(DOCS / f"review_findings_{V}.csv", index=False)
log.info(f"review findings register: {len(RF)} items")
