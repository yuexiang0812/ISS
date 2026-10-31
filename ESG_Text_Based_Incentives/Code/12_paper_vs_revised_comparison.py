"""Step 12 — (e, part 1) Compare the AGHJ (2025) 953-keyword dictionary with the revised classifier v1.0.

Both are applied to the SAME units and years (1998-2021). The paper's rule: a metric is ESG if its metricOther
matches any keyword; blank/no-match = non-ESG (paper_esg_as_used). We also report the paper's implicit
'unknown' (blank metricOther) so Unknown rates are comparable.
Outputs (Validation/): e_overlap_*.csv, e_annual_comparison.csv, e_top_disagreements_local.csv (ISS text, git-ignored)
"""
import numpy as np, pandas as pd
from config import INTER, VALID, get_logger
from dtautil import agg_tri

log = get_logger("12_paper_vs_revised_comparison")
A = pd.read_parquet(INTER / "dataset_A.parquet")
K = pd.read_parquet(INTER / "dataset_B.parquet")
C = pd.read_parquet(INTER / "dataset_C.parquet")
g = pd.read_parquet(INTER / "goal_records.parquet", columns=["text_id", "fiscalYear", "iss_esg_flag", "metricOther_norm"])
lab = lambda s: s.map({1.0: "1", 0.0: "0"}).fillna("Unknown")

# ---- overlap at unit and goal-record level
A["paper"] = A.paper_esg_as_used.map({1: "paper=1", 0: "paper=0"})
A["rev_strict"] = "rev_strict=" + lab(A.esg_strict); A["rev_ext"] = "rev_ext=" + lab(A.esg_extended)
for w, name in [(None, "units"), ("n_goal_rows", "goal_rows")]:
    t1 = pd.crosstab(A.paper, A.rev_strict, values=A[w] if w else None, aggfunc="sum" if w else None, margins=True).fillna(0).astype(int)
    t2 = pd.crosstab(A.paper, A.rev_ext, values=A[w] if w else None, aggfunc="sum" if w else None, margins=True).fillna(0).astype(int)
    t1.to_csv(VALID / f"e_overlap_strict_{name}.csv"); t2.to_csv(VALID / f"e_overlap_extended_{name}.csv")
    log.info(f"overlap ({name}) paper vs revised STRICT:\n{t1}\noverlap ({name}) paper vs revised EXTENDED:\n{t2}")

# ---- annual comparison at goal-record, KPI, grant, executive and firm level
g = g.merge(A[["text_id", "esg_strict", "esg_extended", "paper_esg_as_used"]], on="text_id")
g["blank"] = g.metricOther_norm.eq("")
yr = g.groupby("fiscalYear").agg(goal_rows=("text_id", "size"), blank_metricother_share=("blank", "mean"),
                                 paper_esg_row_share=("paper_esg_as_used", "mean"),
                                 rev_strict_row_share_lb=("esg_strict", lambda s: (s == 1).mean()),
                                 rev_strict_row_share_known=("esg_strict", lambda s: (s == 1).sum() / s.notna().sum()),
                                 rev_unknown_row_share=("esg_strict", lambda s: s.isna().mean()),
                                 rev_ext_row_share_lb=("esg_extended", lambda s: (s == 1).mean()),
                                 iss_esg_row_share_diag=("iss_esg_flag", "mean"))
# grant / executive / firm adoption: paper vs revised vs ISS (diagnostic)
K = K.merge(A[["text_id", "paper_esg_as_used"]], on="text_id")
gp = K.groupby("grantid").paper_esg_as_used.max().rename("grant_paper_esg")
C = C.merge(gp, left_on="grantid", right_index=True, how="left")
C["grant_paper_esg"] = C.grant_paper_esg.fillna(0)
P = C[C.grant_is_perf == 1]
ex = P.groupby(["cik", "fiscalyear", "participantid"]).agg(paper=("grant_paper_esg", "max"), iss=("grant_iss_esg_diag", "max")).reset_index()
ex["rev_strict"] = agg_tri(P, ["cik", "fiscalyear", "participantid"], "grant_esg_strict").values
ex["rev_ext"] = agg_tri(P, ["cik", "fiscalyear", "participantid"], "grant_esg_extended").values
fm = P.groupby(["cik", "fiscalyear"]).agg(paper=("grant_paper_esg", "max"), iss=("grant_iss_esg_diag", "max")).reset_index()
fm["rev_strict"] = agg_tri(P, ["cik", "fiscalyear"], "grant_esg_strict").values
fm["rev_ext"] = agg_tri(P, ["cik", "fiscalyear"], "grant_esg_extended").values
def rates(df, lvl):
    r = df.groupby("fiscalyear").agg(n=("paper", "size"), paper_adopt=("paper", "mean"), iss_adopt_diag=("iss", "mean"),
                                     rev_strict_adopt_lb=("rev_strict", lambda s: (s == 1).mean()),
                                     rev_strict_adopt_known=("rev_strict", lambda s: (s == 1).sum() / max(s.notna().sum(), 1)),
                                     rev_strict_adopt_ub=("rev_strict", lambda s: (s != 0).mean()),
                                     rev_strict_unknown=("rev_strict", lambda s: s.isna().mean()),
                                     rev_ext_adopt_lb=("rev_ext", lambda s: (s == 1).mean()))
    return r.add_prefix(lvl + "_")
out = yr.join(rates(ex, "exec_perf"), how="outer").join(rates(fm, "firm_perf"), how="outer")
out.index.name = "fiscalyear"
out.round(4).to_csv(VALID / "e_annual_comparison.csv")
log.info("annual comparison (2014-2021):\n" + out.loc[2014:2021, ["paper_esg_row_share", "rev_strict_row_share_lb", "rev_unknown_row_share",
         "exec_perf_paper_adopt", "exec_perf_rev_strict_adopt_lb", "exec_perf_rev_strict_adopt_ub", "exec_perf_iss_adopt_diag",
         "firm_perf_paper_adopt", "firm_perf_rev_strict_adopt_lb", "firm_perf_iss_adopt_diag"]].round(3).to_string())

# ---- disagreement listing (contains ISS text -> local)
d = A[(A.paper_esg_as_used == 1) != (A.esg_strict == 1)].sort_values("n_goal_rows", ascending=False)
d[["text_id", "metric", "text_original", "paper_terms", "esg_strict", "esg_extended", "esg_topics", "adjacent_flags", "classification_reason",
   "n_goal_rows", "first_year", "last_year"]].head(1000).to_csv(VALID / "e_top_disagreements_local.csv", index=False)
cat = np.select([(A.paper_esg_as_used == 1) & (A.esg_strict == 1), (A.paper_esg_as_used == 1) & (A.esg_extended == 1),
                 (A.paper_esg_as_used == 1) & A.adjacent_flags.ne(""), (A.paper_esg_as_used == 1) & A.esg_strict.isna(),
                 (A.paper_esg_as_used == 1), (A.esg_strict == 1)],
                ["agree_esg", "paper_esg_rev_extended_only", "paper_esg_rev_adjacent_excluded", "paper_esg_rev_unknown",
                 "paper_esg_rev_non_esg", "paper_non_esg_rev_strict"], "agree_non_esg_or_unknown")
s = A.assign(cat=cat).groupby("cat").agg(units=("text_id", "size"), goal_rows=("n_goal_rows", "sum"))
s.to_csv(VALID / "e_disagreement_categories.csv"); log.info("disagreement categories:\n" + s.to_string())

# ---- v1.1: approximate replication of AGHJ (2025) Table 1 "% ESG Metrics" (2008-2021) as an implementation check
# 中文：用论文口径近似复现其表 1：观测 = 高管-年 x 业绩型股权/期权 grant 中的标准（会计/市场）指标；
# 若该高管当年任一 grant 含论文词典匹配的 ESG 指标，则该观测记为 ESG。论文样本还要求可计算 dollar delta（735 家公司），
# 因此只比较水平与趋势的大致一致性，不期望数值完全相同。
AGHJ_T1 = {2008: 22.9, 2009: 29.0, 2010: 36.6, 2011: 20.2, 2012: 26.8, 2013: 27.1, 2014: 29.9, 2015: 20.4, 2016: 23.7,
           2017: 23.8, 2018: 24.9, 2019: 29.6, 2020: 32.1, 2021: 45.4}
Kr = K.merge(A[["text_id", "rule_ids", "esg_strict"]], on="text_id", how="left")
std = Kr.rule_ids.fillna("").str.contains("N_financial|L01_fin_label|C01_fin_metrictype") & (Kr.esg_strict == 0)
eq = C[(C.grant_is_perf == 1) & C.grant_type.isin(["stock_like", "option_like"])][["grantid", "cik", "fiscalyear", "participantid"]]
obs = Kr[std].merge(eq, on="grantid", suffixes=("_k", "")).drop_duplicates(["cik", "fiscalyear", "participantid", "text_id"])
ex_paper = Kr.merge(C[["grantid", "cik", "fiscalyear", "participantid"]], on="grantid", suffixes=("_k", "")).groupby(
    ["cik", "fiscalyear", "participantid"]).agg(paper=("paper_esg_as_used", "max"), rev=("kpi_esg_strict", lambda s: float((s == 1).any())))
obs = obs.merge(ex_paper, left_on=["cik", "fiscalyear", "participantid"], right_index=True, how="left")
rep = obs[obs.fiscalyear.between(2008, 2021)].groupby("fiscalyear").agg(n_obs=("text_id", "size"), our_paper_dictionary_pct=("paper", "mean"),
                                                                            our_v_strict_lb_pct=("rev", "mean"))
rep[["our_paper_dictionary_pct", "our_v_strict_lb_pct"]] *= 100
rep["aghj_2025_table1_pct"] = rep.index.map(AGHJ_T1)
rep.round(1).to_csv(VALID / "e_paper_replication_benchmark.csv")
log.info("approximate replication of AGHJ (2025) Table 1 (% obs whose executive has an ESG metric):\n" + rep.round(1).to_string())
