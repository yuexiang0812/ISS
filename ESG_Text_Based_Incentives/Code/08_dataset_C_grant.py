"""Step 08 — Dataset C: ESG_Grant_Master.dta (one row per distinct grantID).

中文说明：Grant 层数据集。业绩型 grant = performanceType 为 Abs/Rel/AbsRel；带加速条件的 Time grant 单独标记。
区分“无业绩条件”（Time，可靠地非 ESG）与“业绩目标数据缺失”（未知）。v1.1 修正：
  (1) 141 个重复 grantID（285 行） 的 performanceType 不一致（Abs vs Time 等），按目标数据明确裁定并标记 grant_dup_resolved；
  (2) 申报目标数多于记录目标数时标记 grant_goal_data_incomplete，且在无 ESG 正例时 ESG 记为未知（缺失的目标可能是 ESG）；
  (3) 现金激励的价值在 ISS 中记于 nonEquityTarget（公允价值几乎全缺），新增 grant_value_combined 供价值占比使用；
  (4) 到期日早于授予日的记录加标记；(5) grant_esg_text_ids 记录触发 ESG 的文本编号，便于追溯。

Performance-based grant: performancetype in {Abs, Rel, AbsRel} (ISS GpbaGrant.performanceType; time-based = 'Time').
Hybrid / acceleration: Time grants with accelerated objectives are flagged (grant_time_with_acceleration) and are
NOT counted as performance grants in the primary measure; their ACC KPIs still count as performance conditions
for grant-level ESG linkage.
Grant goal status distinguishes absence of performance conditions from missing goal data:
  perf_with_goals | perf_goals_missing | time_no_perf_condition | time_with_accel_goals | time_accel_declared_goals_missing | type_missing
Grant ESG (Strict/Extended):
  1  at least one KPI = 1
  0  all KPIs = 0, OR time grant without any performance/acceleration condition (no ESG condition can exist)
  .  otherwise (unresolved KPIs, or performance grant whose goal data are missing)
"""
import numpy as np, pandas as pd
from config import INTER, PERF_TYPES, record_stats, read_raw, clean_missing_codes, clean_missing_dates, get_logger, check_unique, check_share
from dtautil import write_dta, share_block
from classify import extended_only_vec

log = get_logger("08_dataset_C_grant")
G = read_raw("grant")
log.info(f"raw grants rows {len(G):,}; distinct grantID {G.grantID.nunique():,}")
gr = pd.read_parquet(INTER / "goal_records.parquet", columns=["grantId", "goal_source", "goal_id", "periodId"])
src = gr.groupby("grantId").goal_source.agg(lambda x: set(x))
# ---- v1.1: duplicated grantIDs carry conflicting performancetype (e.g. 'Abs' and 'Time'); resolve from goal data
dup = G[G.grantID.duplicated(keep=False)]
diffcols = [c for c in G.columns if (dup.groupby("grantID")[c].nunique(dropna=False) > 1).any()]
log.info(f"duplicated grantIDs: {dup.grantID.nunique()} ids / {len(dup)} rows; columns differing within ids: {diffcols}")
types = dup.groupby("grantID").performancetype.agg(lambda x: "/".join(sorted(set(x.fillna("")))))
def resolve(gid):
    s_ = src.get(gid, set())
    if "ABS" in s_ and "REL" in s_: return "AbsRel"
    if "ABS" in s_: return "Abs"
    if "REL" in s_: return "Rel"
    return None
res = {gid: resolve(gid) for gid in types.index}
G = G.drop_duplicates("grantID").copy()
G["grant_dup_resolved"] = G.grantID.isin(types.index).astype("int8")
G["grant_dup_performancetypes"] = G.grantID.map(types).fillna("")
m = G.grantID.isin([k for k, v in res.items() if v])
G.loc[m, "performancetype"] = G.loc[m, "grantID"].map(res)
log.info(f"performancetype resolved from goal data for {int(m.sum())} duplicated grantIDs: {types.value_counts().to_dict()}")
G["grant_date"] = clean_missing_dates(G.grantDate)
G["expiration_date"] = clean_missing_dates(G.expirationDate)
for c in ["grantDateFV", "nonEquityThreshold", "nonEquityTarget", "nonEquityMax", "equityThreshold", "equityTarget", "equityMax",
          "stockAward", "optionAward", "exercisePrice", "vestLowGrant", "vestHighGrant"]:
    raw = pd.to_numeric(G[c], errors="coerce")
    G[c + "_mc"] = (raw <= -9999).astype("int8")
    G[c] = clean_missing_codes(raw)
neg_fv = int((G.grantDateFV < 0).sum()); neg_vh = int((G.vestHighGrant < 0).sum())
log.info(f"impossible values set to missing: negative grantDateFV={neg_fv}, negative vestHighGrant={neg_vh}")
record_stats("08", n_negative_grantdatefv=int(neg_fv), n_negative_vesthighgrant=int(neg_vh))
G.loc[G.grantDateFV < 0, "grantDateFV"] = np.nan; G.loc[G.vestHighGrant < 0, "vestHighGrant"] = np.nan
bad_date = (G.grant_date.notna()) & ((G.grant_date.dt.year < G.FiscalYear - 3) | (G.grant_date.dt.year > G.FiscalYear + 2))
log.info(f"grant dates outside [FY-3, FY+2]: {int(bad_date.sum())} (flagged grant_date_suspect)")
G["grant_date_suspect"] = bad_date.astype("int8")
G["grant_dates_inconsistent"] = (G.expiration_date.notna() & G.grant_date.notna() & (G.expiration_date < G.grant_date)).astype("int8")
log.info(f"expiration date before grant date: {int(G.grant_dates_inconsistent.sum())} (flagged grant_dates_inconsistent)")
# ---- v1.1: combined grant value. ISS records cash-incentive awards' value as target payout (nonEquityTarget);
# grant-date fair value is reported for equity/option awards. Using fair value alone silently drops cash bonus plans.
G["grant_value_combined"] = G.grantDateFV.where(G.grantDateFV.notna(), G.nonEquityTarget)
G["grant_value_source"] = np.select([G.grantDateFV.notna(), G.nonEquityTarget.notna()], ["grant_date_fair_value", "nonequity_target_payout"], "missing")
log.info("grant value source:\n" + G.grant_value_source.value_counts().to_string())
# ---- v1.1: declared vs recorded objectives (partial goal data)
rc = gr.groupby(["grantId", "goal_source"]).agg(rows=("goal_id", "size")).unstack(fill_value=0)
rc.columns = [f"{a}_{b}" for a, b in rc.columns]
G = G.join(rc, on="grantID")
inc = np.zeros(len(G), dtype=bool)
for s_, num in [("ABS", "numAbsolute"), ("REL", "numRelative"), ("ACC", "numAccelerated")]:
    # rows >= distinct objectives, so "declared > recorded rows" is the binding (conservative) condition
    rows_ = G[f"rows_{s_}"].fillna(0) if f"rows_{s_}" in G.columns else pd.Series(0, index=G.index)
    inc |= (G[num].fillna(0) > rows_).values
G["grant_goal_data_incomplete"] = inc.astype("int8")
G = G.drop(columns=[c for c in G.columns if c.startswith("rows_")])
log.info(f"grants whose declared objectives exceed recorded goal rows: {int(inc.sum())} (flagged grant_goal_data_incomplete)")

K = pd.read_parquet(INTER / "dataset_B.parquet")
kc = K.assign(n=1, s1=(K.kpi_esg_strict == 1), s0=(K.kpi_esg_strict == 0), su=K.kpi_esg_strict.isna(),
              x1=(K.kpi_esg_extended == 1), xu=K.kpi_esg_extended.isna(), e1=(K.kpi_esg_e == 1), sS=(K.kpi_esg_s == 1), g1=(K.kpi_esg_g == 1),
              gen=(K.kpi_esg_general == 1) & (K.kpi_esg_strict == 1), eu=K.kpi_esg_e.isna(), suu=K.kpi_esg_s.isna(), gu=K.kpi_esg_g.isna(),
              acc=(K.goal_source == "ACC"), iss=(K.kpi_iss_esg_flag_diag == 1), xo=(K.kpi_esg_extended_only == 1))
agg = kc.groupby("grantid").agg(grant_n_kpis=("n", "sum"), grant_n_esg_kpis_strict=("s1", "sum"), grant_n_non_esg_kpis=("s0", "sum"),
                                grant_n_unknown_kpis=("su", "sum"), grant_n_esg_kpis_extended=("x1", "sum"), grant_n_unknown_kpis_ext=("xu", "sum"),
                                grant_n_extended_only_kpis=("xo", "sum"), grant_n_e_kpis=("e1", "sum"), grant_n_s_kpis=("sS", "sum"),
                                grant_n_g_kpis=("g1", "sum"), grant_n_general_esg_kpis=("gen", "sum"),
                                _eu=("eu", "sum"), _su=("suu", "sum"), _gu=("gu", "sum"), grant_n_acc_kpis=("acc", "sum"),
                                grant_n_iss_esg_kpis_diag=("iss", "sum"), grant_n_goal_records=("kpi_source_count", "sum"))
G = G.merge(agg, left_on="grantID", right_index=True, how="left")
tids = K[K.kpi_esg_strict == 1].groupby("grantid").text_id.agg(lambda x: "|".join(sorted(set(x))))
G["grant_esg_text_ids"] = G.grantID.map(tids).fillna("")
cnt = [c for c in agg.columns]
G[cnt] = G[cnt].fillna(0).astype(int)
orph = set(K.grantid) - set(G.grantID)
log.info(f"KPIs whose grant is absent from grants table: {len(orph)} grants ({int(K.grantid.isin(orph).sum())} KPIs) -> excluded, listed in audit")
pd.DataFrame({"grantid": sorted(orph)}).to_csv(INTER / "audit_goal_grants_missing_in_grant_table.csv", index=False)

pt = G.performancetype.fillna("").str.strip()
G["grant_is_perf"] = pt.isin(PERF_TYPES).astype("int8")
G["grant_is_hybrid_absrel"] = (pt == "AbsRel").astype("int8")
G["grant_time_with_acceleration"] = ((pt == "Time") & ((G.numAccelerated.fillna(0) > 0) | (G.grant_n_acc_kpis > 0))).astype("int8")
has_goal = G.grant_n_kpis > 0
G["grant_goal_status"] = np.select(
    [G.grant_is_perf.eq(1) & has_goal, G.grant_is_perf.eq(1) & ~has_goal,
     pt.eq("Time") & has_goal, pt.eq("Time") & G.numAccelerated.fillna(0).gt(0) & ~has_goal, pt.eq("Time")],
    ["perf_with_goals", "perf_goals_missing", "time_with_accel_goals", "time_accel_declared_goals_missing", "time_no_perf_condition"], "type_missing")
log.info("grant goal status:\n" + G.grant_goal_status.value_counts().to_string())


INCOMPLETE = G.grant_goal_data_incomplete.values == 1


def grant_tri(n_pos, n_unknown, n_k, status):
    out = np.where(n_pos > 0, 1.0, np.where((n_k > 0) & (n_unknown == 0), 0.0, np.nan))
    out = np.where(INCOMPLETE & (n_pos == 0), np.nan, out)          # v1.1: missing objectives could be ESG -> unknown, not 0
    out = np.where(status == "time_no_perf_condition", 0.0, out)      # no performance condition => no ESG condition
    return out

st = G.grant_goal_status.values
G["grant_esg_strict"] = grant_tri(G.grant_n_esg_kpis_strict, G.grant_n_unknown_kpis, G.grant_n_kpis, st)
G["grant_esg_extended"] = grant_tri(G.grant_n_esg_kpis_extended, G.grant_n_unknown_kpis_ext, G.grant_n_kpis, st)
G["grant_esg_extended_only"] = extended_only_vec(G.grant_esg_strict, G.grant_esg_extended)
for p, nk, nu in [("e", "grant_n_e_kpis", "_eu"), ("s", "grant_n_s_kpis", "_su"), ("g", "grant_n_g_kpis", "_gu")]:
    G[f"grant_esg_{p}"] = grant_tri(G[nk], G[nu], G.grant_n_kpis, st)
G["grant_iss_esg_diag"] = np.where(G.grant_n_kpis > 0, (G.grant_n_iss_esg_kpis_diag > 0).astype(float), np.where(st == "time_no_perf_condition", 0.0, np.nan))

ex, lb, ub, cov = share_block(G.grant_n_esg_kpis_strict, G.grant_n_unknown_kpis, G.grant_n_kpis)
G["grant_esg_kpi_share_strict"], G["grant_esg_share_lb"], G["grant_esg_share_ub"], G["grant_classification_coverage"] = ex, lb, ub, cov
ex2, lb2, ub2, _ = share_block(G.grant_n_esg_kpis_extended, G.grant_n_unknown_kpis_ext, G.grant_n_kpis)
G["grant_esg_kpi_share_extended"], G["grant_esg_share_ext_lb"], G["grant_esg_share_ext_ub"] = ex2, lb2, ub2
for p, nu in [("e", "_eu"), ("s", "_su"), ("g", "_gu")]:   # same rule as aggregate.py: exact only if every KPI's pillar is known
    G[f"grant_{p}_kpi_share"], G[f"grant_{p}_kpi_share_lb"], G[f"grant_{p}_kpi_share_ub"], _ = share_block(G[f"grant_n_{p}_kpis"], G[nu], G.grant_n_kpis)
G["grant_classification_complete"] = np.where(st == "time_no_perf_condition", 1,
                                              np.where((G.grant_n_kpis > 0) & ~INCOMPLETE, (G.grant_n_unknown_kpis == 0).astype(int), 0)).astype("int8")
G.loc[st == "time_no_perf_condition", "grant_classification_coverage"] = 1.0

C = G.rename(columns={"grantID": "grantid", "CIK": "cik", "FiscalYear": "fiscalyear", "FiscalMonth": "fiscalmonth", "AwardType": "award_type",
                      "performancetype": "performancetype", "PaidInCash": "paid_in_cash", "grantDateFV": "grant_value",
                      "nonEquityTarget": "nonequity_target", "nonEquityThreshold": "nonequity_threshold", "nonEquityMax": "nonequity_max",
                      "equityTarget": "equity_target", "equityThreshold": "equity_threshold", "equityMax": "equity_max", "stockAward": "stock_award",
                      "optionAward": "option_award", "exercisePrice": "exercise_price", "vestingSchedule": "vesting_schedule",
                      "VestAfterContingency": "vest_after_contingency", "vestLowGrant": "vest_low_grant", "vestHighGrant": "vest_high_grant",
                      "numAbsolute": "num_absolute", "numRelative": "num_relative", "numAccelerated": "num_accelerated",
                      "performanceGrouping": "performance_grouping", "isexchange": "is_exchange", "grantDateFVInferred": "grant_value_inferred",
                      "grantDateFV_mc": "grant_value_missing_code"})
C["grant_type"] = np.where(C.award_type.isin(["cashShort", "cashLong", "unitCash", "Unit Cash"]), "cash_incentive",
                  np.where(C.award_type.isin(["Option", "reloadOption", "phantomOption", "sarCash", "sarEquity"]), "option_like",
                  np.where(C.award_type.isin(["rsu", "stock", "phantomStock", "Performance Unit"]), "stock_like", "other_or_missing")))
keep = ["grantid", "participantid", "cik", "fiscalyear", "fiscalmonth", "award_type", "grant_type", "performancetype", "paid_in_cash",
        "grant_date", "grant_date_suspect", "expiration_date", "grant_dates_inconsistent", "grant_value", "grant_value_missing_code", "grant_value_inferred",
        "grant_value_combined", "grant_value_source", "grant_dup_resolved", "grant_dup_performancetypes", "grant_goal_data_incomplete",
        "nonequity_threshold", "nonequity_target", "nonequity_max", "equity_threshold", "equity_target", "equity_max", "stock_award", "option_award",
        "exercise_price", "vesting_schedule", "vest_after_contingency", "vest_low_grant", "vest_high_grant", "num_absolute", "num_relative",
        "num_accelerated", "performance_grouping", "is_exchange",
        "grant_is_perf", "grant_is_hybrid_absrel", "grant_time_with_acceleration", "grant_goal_status",
        "grant_esg_strict", "grant_esg_extended", "grant_esg_extended_only", "grant_esg_e", "grant_esg_s", "grant_esg_g",
        "grant_n_kpis", "grant_n_esg_kpis_strict", "grant_n_esg_kpis_extended", "grant_n_extended_only_kpis", "grant_n_e_kpis", "grant_n_s_kpis",
        "grant_n_g_kpis", "grant_n_general_esg_kpis", "grant_n_non_esg_kpis", "grant_n_unknown_kpis", "grant_n_unknown_kpis_ext", "grant_n_acc_kpis",
        "grant_n_goal_records", "grant_esg_kpi_share_strict", "grant_esg_kpi_share_extended", "grant_e_kpi_share", "grant_s_kpi_share", "grant_g_kpi_share",
        "grant_e_kpi_share_lb", "grant_e_kpi_share_ub", "grant_s_kpi_share_lb", "grant_s_kpi_share_ub", "grant_g_kpi_share_lb", "grant_g_kpi_share_ub",
        "grant_classification_complete", "grant_classification_coverage", "grant_esg_share_lb", "grant_esg_share_ub",
        "grant_esg_share_ext_lb", "grant_esg_share_ext_ub", "grant_iss_esg_diag", "grant_n_iss_esg_kpis_diag", "grant_esg_text_ids"]
C = C[keep]
check_unique(C, ["grantid"], "grant master", log)
check_share(C, [c for c in keep if "share" in c or "coverage" in c], log, "grant")
assert (C.grant_n_esg_kpis_strict + C.grant_n_non_esg_kpis + C.grant_n_unknown_kpis == C.grant_n_kpis).all(), "KPI count identity"
assert C.grant_n_kpis.sum() == K.grantid.isin(C.grantid).sum(), "grant KPI total != KPI master"
log.info("identity checks passed: esg+non+unknown = n_kpis; KPI totals reconcile to KPI master")
log.info("grant_esg_strict by status:\n" + pd.crosstab(C.grant_goal_status, C.grant_esg_strict.fillna(-1)).to_string())
C.to_parquet(INTER / "dataset_C.parquet", index=False)
L = {c: c for c in keep}
L.update(dict(grantid="ISS grantID", participantid="ISS participantID", cik="Company CIK", fiscalyear="Fiscal year", fiscalmonth="Fiscal month",
              award_type="ISS awardType", grant_type="cash_incentive/option_like/stock_like", performancetype="ISS performanceType Abs/Rel/AbsRel/Time",
              grant_value="Grant-date fair value (USD; -9999 codes -> .)", grant_date_suspect="Grant date outside [FY-3, FY+2]",
              grant_is_perf="1 if performance-vesting (Abs/Rel/AbsRel)", grant_is_hybrid_absrel="1 if both absolute and relative goals",
              grant_time_with_acceleration="1 if time-based with performance acceleration", grant_goal_status="Goal availability status",
              grant_esg_strict="Grant has Strict ESG condition 1/0/.", grant_esg_extended="Grant has Extended ESG condition 1/0/.",
              grant_esg_extended_only="Extended but not Strict 1/0/.", grant_esg_e="Grant has E condition 1/0/.", grant_esg_s="Grant has S condition 1/0/.",
              grant_esg_g="Grant has G condition 1/0/.", grant_n_kpis="Distinct KPIs in grant", grant_n_general_esg_kpis="Strict KPIs with multi-pillar ESG term",
              grant_esg_kpi_share_strict="Strict ESG KPI share (. if any KPI unknown)", grant_esg_share_lb="Strict ESG KPI share lower bound",
              grant_esg_share_ub="Strict ESG KPI share upper bound", grant_classification_coverage="Share of KPIs with known Strict label",
              grant_classification_complete="1 if all KPIs classified (or no perf condition)", grant_iss_esg_diag="DIAGNOSTIC: ISS ESG category present",
              grant_value_combined="Fair value; if missing, non-equity target payout (cash awards)", grant_value_source="Source of grant_value_combined",
              grant_dup_resolved="1 if grantID duplicated in raw file (type resolved from goals)", grant_dup_performancetypes="Raw performancetype values of duplicate",
              grant_goal_data_incomplete="1 if declared objectives exceed recorded goal rows", grant_dates_inconsistent="1 if expiration date before grant date",
              grant_esg_text_ids="text_ids of Strict ESG KPIs (trace to Dataset A)"))
write_dta(C, "ESG_Grant_Master.dta", L, log, keys=["grantid"])
