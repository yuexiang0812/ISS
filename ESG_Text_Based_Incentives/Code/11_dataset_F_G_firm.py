"""Step 11 — Dataset F (ESG_Firm_Year_Master.dta) and Dataset G (ESG_NonCEO_Firm_Year.dta).

中文说明：公司-年主表（研究主数据集）与非 CEO 公司-年表。公司-年全集 = CompanyFY；无 grant 的公司-年计数为 0、指标缺失（=不适用）。
非 CEO 仅包括 currentCEO 明确为 0、且所在公司-年已识别出 CEO 的高管；角色不明者排除并计数。v1.1 新增 firm_multi_fiscalmonth
（grant 的财政月与 CompanyFY 不一致或同一财年出现多个财政月，例如财年截止日变更）。

F universe: every (CIK, fiscalyear) in CompanyFY plus any firm-year that appears only in the grants table.
    Firm-years with no grants keep firm_has_grants = 0 and missing ESG measures ('not applicable', not 0).
G: grants of executives who are reliably NON-CEO: the firm-year has an identified CEO (unique or multiple currentCEO flags),
   the executive is not a CEO candidate, and currentCEO is explicitly 0. Executives with missing currentCEO, or in
   firm-years without an identified CEO, are excluded and counted in nonceo_n_role_unknown_execs.
"""
import numpy as np, pandas as pd
from config import INTER, read_raw, clean_missing_dates, get_logger, check_unique
from dtautil import write_dta
from aggregate import aggregate, check_aggregate, fill_counts

log = get_logger("11_dataset_F_G_firm")
C = pd.read_parquet(INTER / "dataset_C.parquet")
K = pd.read_parquet(INTER / "dataset_B_with_topics.parquet")
D = pd.read_parquet(INTER / "dataset_D.parquet")
E = pd.read_parquet(INTER / "dataset_E.parquet")
fys = pd.read_parquet(INTER / "ceo_status_firmyear.parquet")
fyk = ["cik", "fiscalyear"]

# ---------------- F
co = read_raw("company").rename(columns={"CIK": "cik", "fiscalYear": "fiscalyear", "fiscalMonth": "fiscalmonth", "companyName": "company_name",
                                          "CUSIP": "cusip", "fiscalYearEnd": "fiscal_year_end", "filingDate": "filing_date", "type": "proxy_form_type"})
co["fiscal_year_end"] = clean_missing_dates(co.fiscal_year_end)
check_unique(co, fyk, "CompanyFY", log)
agg = aggregate(C, K, fyk, "firm")
F = co[fyk + ["fiscalmonth", "company_name", "ticker", "cusip", "fiscal_year_end", "proxy_form_type"]].merge(agg, on=fyk, how="outer", indicator=True)
log.info(f"firm-year merge CompanyFY vs grants: {F._merge.value_counts().to_dict()}")
F["firm_in_companyfy"] = F._merge.isin(["both", "left_only"]).astype("int8"); F = F.drop(columns="_merge")
F["firm_has_grants"] = F.firm_n_grants.fillna(0).gt(0).astype("int8")
F["firm_has_perf_grants"] = F.firm_n_perf_grants.fillna(0).gt(0).astype("int8")
F = fill_counts(F, "firm")     # v1.1: every count variable 0 (not missing) for firm-years without grants
fmg = C.groupby(fyk).fiscalmonth.agg(lambda x: set(x.dropna()))
F["firm_multi_fiscalmonth"] = [int(len(fmg.get((c, y), set()) | ({m} if pd.notna(m) else set())) > 1) for c, y, m in zip(F.cik, F.fiscalyear, F.fiscalmonth)]
log.info(f"firm-years whose grants' fiscal month differs from CompanyFY or spans >1 month: {int(F.firm_multi_fiscalmonth.sum())}")
F = F.merge(fys[fyk + ["ceo_identification_status"]].rename(columns={"ceo_identification_status": "firm_ceo_identification_status"}), on=fyk, how="left")
check_unique(F, fyk, "Firm-Year", log)
check_aggregate(F[F.firm_has_grants == 1], "firm", log, "firm")
assert F.firm_n_grants.sum() == len(C), "firm grant counts do not reconcile"
# aggregation identity: firm ESG grant count = sum over executives
x = D.groupby(fyk)[["exec_n_esg_grants_strict", "exec_n_grants", "exec_n_perf_grants"]].sum()
y = F.set_index(fyk).loc[x.index, ["firm_n_esg_grants_strict", "firm_n_grants", "firm_n_perf_grants"]]
assert (x.values == y.values).all(), "firm vs executive grant aggregation identity failed"
log.info("reconciliation: firm grant/perf/ESG-grant counts = sums over executive-years; total grants = grant master")
F.to_parquet(INTER / "dataset_F.parquet", index=False)
LF = dict(cik="Company CIK", fiscalyear="Fiscal year", fiscalmonth="Fiscal month (CompanyFY)", company_name="Company name (CompanyFY)",
          ticker="Ticker (CompanyFY)", cusip="CUSIP (CompanyFY)", firm_in_companyfy="1 if firm-year in CompanyFY", firm_has_grants="1 if >=1 grant",
          firm_has_perf_grants="1 if >=1 performance grant", firm_esg_adopt_strict="Any grant with Strict ESG condition 1/0/.",
          firm_perf_esg_adopt_strict="Any performance grant with Strict ESG condition 1/0/.",
          firm_esg_perf_grant_share_strict="Perf grants with Strict ESG / perf grants (. if unresolved)",
          firm_esg_perf_share_lb="Perf-grant Strict ESG share lower bound", firm_esg_perf_share_ub="Perf-grant Strict ESG share upper bound",
          firm_esg_kpi_share_strict="Distinct Strict ESG KPIs / distinct KPIs (. if unresolved)",
          firm_ceo_identification_status="CEO identification status of firm-year", firm_iss_esg_adopt_diag="DIAGNOSTIC: ISS ESG category in any grant",
          firm_multi_fiscalmonth="1 if grants span >1 fiscal month or differ from CompanyFY month")
write_dta(F, "ESG_Firm_Year_Master.dta", LF, log, keys=fyk)

# ---------------- G
ident = fys[fys.ceo_identification_status.isin(["unique_current_ceo_flag", "multiple_current_ceo_flags"])][fyk]
ceo_ids = E[["cik", "fiscalyear", "participantid"]].assign(_ceo=1)
d = D.merge(ident.assign(_id=1), on=fyk, how="left").merge(ceo_ids, on=fyk + ["participantid"], how="left")
d["_id"] = d._id.fillna(0); d["_ceo"] = d._ceo.fillna(0)
d["role_class"] = np.select([d._ceo == 1, (d._id == 1) & (d.exec_current_ceo_flag == 0)], ["ceo", "nonceo"], "role_unknown")
log.info("executive role classes:\n" + d.role_class.value_counts().to_string())
non = d[d.role_class == "nonceo"][fyk + ["participantid"]]
Cn = C.merge(non, on=fyk + ["participantid"], how="inner")
G = fill_counts(aggregate(Cn, K, fyk, "nonceo"), "nonceo")
ne = non.groupby(fyk).size().rename("nonceo_n_executives")
ru = d[d.role_class == "role_unknown"].groupby(fyk).size().rename("nonceo_n_role_unknown_execs")
G = G.merge(ne, on=fyk, how="left").merge(ru, on=fyk, how="left").fillna({"nonceo_n_role_unknown_execs": 0})
G["nonceo_role_uncertainty_flag"] = (G.nonceo_n_role_unknown_execs > 0).astype("int8")
check_unique(G, fyk, "NonCEO-Firm-Year", log)
check_aggregate(G, "nonceo", log, "non-CEO")
G.to_parquet(INTER / "dataset_G.parquet", index=False)
LG = dict(cik="Company CIK", fiscalyear="Fiscal year", nonceo_n_executives="Reliably identified non-CEO executives with grants",
          nonceo_n_role_unknown_execs="Executives excluded: CEO status unknown", nonceo_role_uncertainty_flag="1 if some executives have unknown role")
write_dta(G, "ESG_NonCEO_Firm_Year.dta", LG, log, keys=fyk)
