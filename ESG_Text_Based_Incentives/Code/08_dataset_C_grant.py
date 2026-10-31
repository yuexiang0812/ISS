"""Step 08 — Dataset C: ESG_Grant_Master.dta (one row per distinct grantID).

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
from config import INTER, PERF_TYPES, read_raw, clean_missing_codes, clean_missing_dates, get_logger, check_unique, check_share
from dtautil import write_dta, share_block

log = get_logger("08_dataset_C_grant")
G = read_raw("grant")
log.info(f"raw grants rows {len(G):,}; distinct grantID {G.grantID.nunique():,}")
G = G.drop_duplicates("grantID").copy()
G["grant_date"] = clean_missing_dates(G.grantDate)
G["expiration_date"] = clean_missing_dates(G.expirationDate)
for c in ["grantDateFV", "nonEquityThreshold", "nonEquityTarget", "nonEquityMax", "equityThreshold", "equityTarget", "equityMax",
          "stockAward", "optionAward", "exercisePrice", "vestLowGrant", "vestHighGrant"]:
    raw = pd.to_numeric(G[c], errors="coerce")
    G[c + "_mc"] = (raw <= -9999).astype("int8")
    G[c] = clean_missing_codes(raw)
neg_fv = int((G.grantDateFV < 0).sum()); neg_vh = int((G.vestHighGrant < 0).sum())
log.info(f"impossible values set to missing: negative grantDateFV={neg_fv}, negative vestHighGrant={neg_vh}")
G.loc[G.grantDateFV < 0, "grantDateFV"] = np.nan; G.loc[G.vestHighGrant < 0, "vestHighGrant"] = np.nan
bad_date = (G.grant_date.notna()) & ((G.grant_date.dt.year < G.FiscalYear - 3) | (G.grant_date.dt.year > G.FiscalYear + 2))
log.info(f"grant dates outside [FY-3, FY+2]: {int(bad_date.sum())} (flagged grant_date_suspect)")
G["grant_date_suspect"] = bad_date.astype("int8")

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


def grant_tri(n_pos, n_unknown, n_k, status):
    out = np.where(n_pos > 0, 1.0, np.where((n_k > 0) & (n_unknown == 0), 0.0, np.nan))
    out = np.where(status == "time_no_perf_condition", 0.0, out)      # no performance condition => no ESG condition
    return out

st = G.grant_goal_status.values
G["grant_esg_strict"] = grant_tri(G.grant_n_esg_kpis_strict, G.grant_n_unknown_kpis, G.grant_n_kpis, st)
G["grant_esg_extended"] = grant_tri(G.grant_n_esg_kpis_extended, G.grant_n_unknown_kpis_ext, G.grant_n_kpis, st)
G["grant_esg_extended_only"] = np.where(G.grant_esg_extended.isna(), np.nan, ((G.grant_esg_extended == 1) & (G.grant_esg_strict != 1)).astype(float))
G["grant_esg_extended_only"] = np.where((G.grant_esg_extended == 0) | ((G.grant_esg_extended == 1) & (G.grant_esg_strict == 1)), 0.0,
                                        np.where((G.grant_esg_extended == 1) & (G.grant_esg_strict == 0), 1.0, np.nan))
for p, nk, nu in [("e", "grant_n_e_kpis", "_eu"), ("s", "grant_n_s_kpis", "_su"), ("g", "grant_n_g_kpis", "_gu")]:
    G[f"grant_esg_{p}"] = grant_tri(G[nk], G[nu], G.grant_n_kpis, st)
G["grant_iss_esg_diag"] = np.where(G.grant_n_kpis > 0, (G.grant_n_iss_esg_kpis_diag > 0).astype(float), np.where(st == "time_no_perf_condition", 0.0, np.nan))

ex, lb, ub, cov = share_block(G.grant_n_esg_kpis_strict, G.grant_n_unknown_kpis, G.grant_n_kpis)
G["grant_esg_kpi_share_strict"], G["grant_esg_share_lb"], G["grant_esg_share_ub"], G["grant_classification_coverage"] = ex, lb, ub, cov
ex2, lb2, ub2, _ = share_block(G.grant_n_esg_kpis_extended, G.grant_n_unknown_kpis_ext, G.grant_n_kpis)
G["grant_esg_kpi_share_extended"], G["grant_esg_share_ext_lb"], G["grant_esg_share_ext_ub"] = ex2, lb2, ub2
for p in "esg":
    G[f"grant_{p}_kpi_share"] = np.where((G.grant_n_kpis > 0) & (G.grant_n_unknown_kpis == 0), G[f"grant_n_{p}_kpis"] / G.grant_n_kpis.where(G.grant_n_kpis > 0), np.nan)
G["grant_classification_complete"] = np.where(st == "time_no_perf_condition", 1, np.where(G.grant_n_kpis > 0, (G.grant_n_unknown_kpis == 0).astype(int), 0)).astype("int8")
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
        "grant_date", "grant_date_suspect", "expiration_date", "grant_value", "grant_value_missing_code", "grant_value_inferred",
        "nonequity_threshold", "nonequity_target", "nonequity_max", "equity_threshold", "equity_target", "equity_max", "stock_award", "option_award",
        "exercise_price", "vesting_schedule", "vest_after_contingency", "vest_low_grant", "vest_high_grant", "num_absolute", "num_relative",
        "num_accelerated", "performance_grouping", "is_exchange",
        "grant_is_perf", "grant_is_hybrid_absrel", "grant_time_with_acceleration", "grant_goal_status",
        "grant_esg_strict", "grant_esg_extended", "grant_esg_extended_only", "grant_esg_e", "grant_esg_s", "grant_esg_g",
        "grant_n_kpis", "grant_n_esg_kpis_strict", "grant_n_esg_kpis_extended", "grant_n_extended_only_kpis", "grant_n_e_kpis", "grant_n_s_kpis",
        "grant_n_g_kpis", "grant_n_general_esg_kpis", "grant_n_non_esg_kpis", "grant_n_unknown_kpis", "grant_n_unknown_kpis_ext", "grant_n_acc_kpis",
        "grant_n_goal_records", "grant_esg_kpi_share_strict", "grant_esg_kpi_share_extended", "grant_e_kpi_share", "grant_s_kpi_share", "grant_g_kpi_share",
        "grant_classification_complete", "grant_classification_coverage", "grant_esg_share_lb", "grant_esg_share_ub",
        "grant_esg_share_ext_lb", "grant_esg_share_ext_ub", "grant_iss_esg_diag", "grant_n_iss_esg_kpis_diag"]
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
              grant_classification_complete="1 if all KPIs classified (or no perf condition)", grant_iss_esg_diag="DIAGNOSTIC: ISS ESG category present"))
write_dta(C, "ESG_Grant_Master.dta", L, log, keys=["grantid"])
