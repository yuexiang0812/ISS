"""Step 14 — Annual statistics 1998-2021 and analysis of the 2018 ISS classification break.

Adoption rates are reported three ways for every unit (firm / executive / CEO):
  _lb  = share with adoption = 1 among all units with performance grants (unknown counted as 0)
  _cc  = share with adoption = 1 among units whose adoption is known (complete case)
  _ub  = share with adoption != 0 (unknown counted as 1)
Outputs: Annual_Analysis/*.csv and annual_trends_report.md
"""
import numpy as np, pandas as pd
from config import INTER, ANNUAL, get_logger

log = get_logger("14_annual_trends")
F = pd.read_parquet(INTER / "dataset_F.parquet"); D = pd.read_parquet(INTER / "dataset_D.parquet")
E = pd.read_parquet(INTER / "dataset_E.parquet"); K = pd.read_parquet(INTER / "dataset_B.parquet")
g = pd.read_parquet(INTER / "goal_records.parquet", columns=["fiscalYear", "metricOther_norm", "text_id", "iss_esg_flag"])
A = pd.read_parquet(INTER / "dataset_A.parquet", columns=["text_id", "esg_strict"])


def rate3(s):
    return pd.Series(dict(lb=(s == 1).mean(), cc=(s == 1).sum() / max(s.notna().sum(), 1), ub=(s != 0).mean(), unknown=s.isna().mean()))


def annual(df, p, extra_filter=None):
    d = df[df[f"{p}_n_perf_grants"] > 0] if extra_filter is None else df[extra_filter & (df[f"{p}_n_perf_grants"] > 0)]
    rows = []
    for y, x in d.groupby("fiscalyear"):
        r = dict(fiscalyear=int(y), n_units_with_perf_grants=len(x))
        for v, name in [(f"{p}_perf_esg_adopt_strict", "adopt_strict"), (f"{p}_perf_esg_adopt_extended", "adopt_ext"),
                        (f"{p}_esg_e_adopt", "adopt_E"), (f"{p}_esg_s_adopt", "adopt_S"), (f"{p}_esg_g_adopt", "adopt_G")]:
            for k, val in rate3(x[v]).items():
                if name.startswith("adopt_") and name[-1] in "ESG" and k in ("cc", "ub"):
                    continue
                r[f"{name}_{k}"] = val
        r["perf_grant_share_strict_mean_complete"] = x[f"{p}_esg_perf_grant_share_strict"].mean()
        r["perf_grant_share_lb_mean"] = x[f"{p}_esg_perf_share_lb"].mean(); r["perf_grant_share_ub_mean"] = x[f"{p}_esg_perf_share_ub"].mean()
        r["kpi_share_lb_mean"] = x[f"{p}_esg_kpi_share_lb"].mean(); r["kpi_share_ub_mean"] = x[f"{p}_esg_kpi_share_ub"].mean()
        r["perf_classification_coverage_mean"] = x[f"{p}_perf_classification_coverage"].mean()
        r["share_units_measurement_complete"] = x[f"{p}_esg_measurement_complete"].mean()
        r["iss_esg_adopt_diag"] = x[f"{p}_iss_esg_adopt_diag"].mean()
        rows.append(r)
    return pd.DataFrame(rows)

firm = annual(F, "firm"); firm.to_csv(ANNUAL / "annual_firm_year.csv", index=False)
execu = annual(D, "exec"); execu.to_csv(ANNUAL / "annual_executive_year.csv", index=False)
ceo = annual(E, "ceo", E.ceo_strict_sample == 1); ceo.to_csv(ANNUAL / "annual_ceo_year_strict_sample.csv", index=False)
cols = ["fiscalyear", "n_units_with_perf_grants", "adopt_strict_lb", "adopt_strict_cc", "adopt_strict_ub", "adopt_ext_lb", "perf_grant_share_lb_mean",
        "kpi_share_lb_mean", "perf_classification_coverage_mean", "iss_esg_adopt_diag"]
log.info("FIRM-YEAR annual:\n" + firm[cols].round(3).to_string(index=False))
log.info("CEO (strict sample) annual:\n" + ceo[cols].round(3).to_string(index=False))

# ---- text availability / classification coverage by year (goal-record level)
g = g.merge(A, on="text_id")
cov = g.groupby("fiscalYear").agg(goal_rows=("text_id", "size"), metricother_blank_share=("metricOther_norm", lambda s: (s == "").mean()),
                                  unknown_share=("esg_strict", lambda s: s.isna().mean()), strict_share=("esg_strict", lambda s: (s == 1).mean()),
                                  iss_esg_share_diag=("iss_esg_flag", "mean")).reset_index()
cov.to_csv(ANNUAL / "annual_text_coverage.csv", index=False)

# ---- 2018 break: (2) ISS vs text at KPI level
K["yr"] = K.fiscalyear
t = K[K.yr.between(2014, 2021)]
iss_vs = pd.crosstab([t.yr, t.kpi_iss_esg_flag_diag.map({1: "ISS_ESG", 0: "ISS_nonESG"})],
                     t.kpi_esg_strict.map({1.0: "text_strict1", 0.0: "text_strict0"}).fillna("text_unknown"))
iss_vs.to_csv(ANNUAL / "break_iss_vs_text_kpi_2014_2021.csv")
log.info("ISS (diag) vs text Strict, KPI counts 2014-2021:\n" + iss_vs.to_string())

# ---- (3)(4) sample composition and continuing firms
Fp = F[F.firm_n_perf_grants > 0][["cik", "fiscalyear", "firm_perf_esg_adopt_strict", "firm_esg_perf_share_lb"]]
s17 = set(Fp[Fp.fiscalyear == 2017].cik); s18 = set(Fp[Fp.fiscalyear == 2018].cik)
comp = dict(firms_2017=len(s17), firms_2018=len(s18), continuing=len(s17 & s18), exits_after_2017=len(s17 - s18), entrants_2018=len(s18 - s17))
cont = Fp[Fp.cik.isin(s17 & s18)]
for grp, ids in [("continuing_2017_2018", s17 & s18), ("exits_after_2017", s17 - s18), ("entrants_2018", s18 - s17)]:
    for y in (2017, 2018):
        x = Fp[(Fp.fiscalyear == y) & Fp.cik.isin(ids)].firm_perf_esg_adopt_strict
        if len(x):
            comp[f"{grp}_{y}_adopt_lb"] = round((x == 1).mean(), 4); comp[f"{grp}_{y}_n"] = len(x)
bal = Fp.pivot_table(index="cik", columns="fiscalyear", values="firm_perf_esg_adopt_strict", aggfunc="first")
bal_ids = bal[[y for y in range(2015, 2022)]].dropna(how="any", subset=None).index if all(y in bal for y in range(2015, 2022)) else []
panel = Fp[Fp.cik.isin(bal[[y for y in range(2015, 2022)]].notna().all(axis=1).loc[lambda s: s].index)]
bp = panel.groupby("fiscalyear").firm_perf_esg_adopt_strict.apply(lambda s: (s == 1).mean()).loc[2015:2021]
comp["balanced_panel_2015_2021_firms"] = int(panel.cik.nunique())
pd.Series(comp).to_csv(ANNUAL / "break_sample_composition_2017_2018.csv")
bp.rename("adopt_strict_lb_balanced_known_2015_2021").to_csv(ANNUAL / "break_balanced_panel_2015_2021.csv")
log.info(f"composition: {comp}\nbalanced panel (firms with known adoption every year 2015-2021) adoption:\n{bp.round(3).to_string()}")

# ---- (5) extensive vs intensive margin (firm perf-grant ESG share, lower bound)
x = F[F.firm_n_perf_grants > 0].groupby("fiscalyear").apply(lambda d: pd.Series(dict(
    mean_share_lb=d.firm_esg_perf_share_lb.mean(), adopt_rate_lb=(d.firm_perf_esg_adopt_strict == 1).mean(),
    intensity_among_adopters=d.loc[d.firm_perf_esg_adopt_strict == 1, "firm_esg_perf_share_lb"].mean())))
dec = []
for y0, y1 in [(2015, 2017), (2017, 2018), (2018, 2021), (2017, 2021)]:
    a0, a1, i0, i1 = x.loc[y0, "adopt_rate_lb"], x.loc[y1, "adopt_rate_lb"], x.loc[y0, "intensity_among_adopters"], x.loc[y1, "intensity_among_adopters"]
    dec.append(dict(period=f"{y0}-{y1}", d_mean_share=x.loc[y1, "mean_share_lb"] - x.loc[y0, "mean_share_lb"],
                    extensive=(a1 - a0) * (i0 + i1) / 2, intensive=(i1 - i0) * (a0 + a1) / 2))
pd.DataFrame(dec).to_csv(ANNUAL / "break_extensive_intensive_decomposition.csv", index=False)
x.to_csv(ANNUAL / "break_margins_by_year.csv")
log.info("extensive/intensive decomposition of mean perf-grant ESG share (lb):\n" + pd.DataFrame(dec).round(4).to_string(index=False))
log.info("text coverage by year:\n" + cov.round(3).to_string(index=False))
