"""Common aggregation of grants and KPIs to any unit (executive-year, CEO-year, firm-year, non-CEO firm-year).

Definitions (identical at every level; prefix p = exec / ceo / firm / nonceo):
  Universe ALL      = all grants of the unit (time-based grants without performance conditions are reliably non-ESG).
  Universe PERF     = performance-vesting grants (performancetype Abs/Rel/AbsRel).
  Adoption          = 1 if >=1 grant in universe has ESG=1; 0 if all grants ESG=0; . otherwise / if universe empty.
  Grant share       = #ESG grants / #grants in universe, reported only if no grant is unresolved;
                      _lb = #ESG / N, _ub = (#ESG + #unknown) / N, coverage = #known / N.
  KPI share         = distinct ESG KPIs / distinct KPIs, distinct KPI = (goal_source, text_id) within the unit,
                      i.e. the same metric text used in several grants of the unit is counted once.
  E/S/G grant share = # performance grants with a confirmed E (S, G) condition / # performance grants (lower bound when
                      general ESG terms leave the pillar unresolved).
  Value share       = grant-date fair value of grants containing >=1 Strict ESG condition / fair value of all grants with
                      reported value (NOT value attributable to ESG; KPI weights are not reliably observable).
"""
import numpy as np, pandas as pd
from dtautil import share_block


def _tri(n_pos, n_zero, n):
    return np.where(n_pos > 0, 1.0, np.where((n > 0) & (n_zero == n), 0.0, np.nan))


def aggregate(C, K, by, p):
    """C: grant table with `by` columns; K: KPI table with grantid (+ by columns merged here)."""
    g = C.assign(
        _n=1, _perf=C.grant_is_perf.eq(1),
        _s1=C.grant_esg_strict.eq(1), _s0=C.grant_esg_strict.eq(0), _su=C.grant_esg_strict.isna(),
        _x1=C.grant_esg_extended.eq(1), _x0=C.grant_esg_extended.eq(0), _xu=C.grant_esg_extended.isna(),
        _e1=C.grant_esg_e.eq(1), _sS1=C.grant_esg_s.eq(1), _g1=C.grant_esg_g.eq(1),
        _val=C.grant_value.where(C.grant_value.notna(), np.nan), _hasval=C.grant_value.notna(),
        _iss=C.grant_iss_esg_diag.eq(1), _accel=C.grant_time_with_acceleration.eq(1))
    for f in ["_s1", "_s0", "_su", "_x1", "_x0", "_xu", "_e1", "_sS1", "_g1"]:
        g[f + "p"] = g[f] & g._perf
    g["_val_esg"] = np.where(g._s1, g.grant_value.fillna(0), 0.0)
    g["_valp"] = np.where(g._perf, g.grant_value.fillna(0), 0.0); g["_hasvalp"] = g._hasval & g._perf
    g["_val_esgp"] = np.where(g._s1 & g._perf, g.grant_value.fillna(0), 0.0)
    g["_valall"] = g.grant_value.fillna(0)
    s = g.groupby(by).agg(**{k: (k, "sum") for k in ["_n", "_perf", "_s1", "_s0", "_su", "_x1", "_x0", "_xu", "_e1", "_sS1", "_g1",
                                                      "_s1p", "_s0p", "_sup", "_x1p", "_x0p", "_xup", "_e1p", "_sS1p", "_g1p",
                                                      "_val_esg", "_valall", "_hasval", "_valp", "_hasvalp", "_val_esgp", "_iss", "_accel"]})
    o = pd.DataFrame(index=s.index)
    o[f"{p}_n_grants"] = s._n; o[f"{p}_n_perf_grants"] = s._perf; o[f"{p}_n_time_accel_grants"] = s._accel
    o[f"{p}_n_esg_grants_strict"] = s._s1; o[f"{p}_n_esg_grants_extended"] = s._x1; o[f"{p}_n_unknown_grants"] = s._su
    o[f"{p}_n_unknown_grants_ext"] = s._xu
    o[f"{p}_n_perf_esg_grants_strict"] = s._s1p; o[f"{p}_n_perf_esg_grants_extended"] = s._x1p; o[f"{p}_n_perf_unknown_grants"] = s._sup
    o[f"{p}_esg_adopt_strict"] = _tri(s._s1, s._s0, s._n)
    o[f"{p}_esg_adopt_extended"] = _tri(s._x1, s._x0, s._n)
    o[f"{p}_perf_esg_adopt_strict"] = _tri(s._s1p, s._s0p, s._perf)
    o[f"{p}_perf_esg_adopt_extended"] = _tri(s._x1p, s._x0p, s._perf)
    o[f"{p}_esg_e_adopt"] = np.where(s._e1p > 0, 1.0, np.where((s._perf > 0) & (s._s0p == s._perf), 0.0, np.nan))
    o[f"{p}_esg_s_adopt"] = np.where(s._sS1p > 0, 1.0, np.where((s._perf > 0) & (s._s0p == s._perf), 0.0, np.nan))
    o[f"{p}_esg_g_adopt"] = np.where(s._g1p > 0, 1.0, np.where((s._perf > 0) & (s._s0p == s._perf), 0.0, np.nan))
    for univ, npos, nunk, ntot in [("all", "_s1", "_su", "_n"), ("perf", "_s1p", "_sup", "_perf")]:
        ex, lb, ub, cov = share_block(s[npos], s[nunk], s[ntot])
        o[f"{p}_esg_{univ}_grant_share_strict"] = ex; o[f"{p}_esg_{univ}_share_lb"] = lb; o[f"{p}_esg_{univ}_share_ub"] = ub
        o[f"{p}_{univ}_classification_coverage"] = cov
    for univ, npos, nunk, ntot in [("all", "_x1", "_xu", "_n"), ("perf", "_x1p", "_xup", "_perf")]:
        ex, lb, ub, _ = share_block(s[npos], s[nunk], s[ntot])
        o[f"{p}_esg_{univ}_grant_share_extended"] = ex; o[f"{p}_esg_{univ}_ext_share_lb"] = lb; o[f"{p}_esg_{univ}_ext_share_ub"] = ub
    with np.errstate(divide="ignore", invalid="ignore"):
        for q, col in [("e", "_e1p"), ("s", "_sS1p"), ("g", "_g1p")]:
            o[f"{p}_{q}_grant_share"] = np.where(s._perf > 0, s[col] / s._perf, np.nan)
        o[f"{p}_total_grant_value"] = np.where(s._hasval > 0, s._valall, np.nan)
        o[f"{p}_esg_compensation_value_share"] = np.where(s._valall > 0, s._val_esg / s._valall, np.nan)
        o[f"{p}_perf_esg_compensation_value_share"] = np.where(s._valp > 0, s._val_esgp / s._valp, np.nan)
        o[f"{p}_value_coverage"] = np.where(s._n > 0, s._hasval / s._n, np.nan)
    o[f"{p}_iss_esg_adopt_diag"] = np.where(s._n > 0, (s._iss > 0).astype(float), np.nan)

    # ---- KPI level (distinct KPI = (goal_source, text_id) within unit)
    kk = K.drop(columns=[c for c in by if c in K.columns]).merge(C[["grantid"] + by], on="grantid", how="inner")
    kk = kk.drop_duplicates(by + ["goal_source", "text_id"])
    kk = kk.assign(_n=1, _s1=kk.kpi_esg_strict.eq(1), _su=kk.kpi_esg_strict.isna(), _x1=kk.kpi_esg_extended.eq(1),
                   _xu=kk.kpi_esg_extended.isna(), _e1=kk.kpi_esg_e.eq(1), _sS1=kk.kpi_esg_s.eq(1), _g1=kk.kpi_esg_g.eq(1))
    t = kk.groupby(by).agg(**{k: (k, "sum") for k in ["_n", "_s1", "_su", "_x1", "_xu", "_e1", "_sS1", "_g1"]})
    ks = kk[kk._s1].assign(_tp=kk.loc[kk._s1, "esg_topics_strict"].str.split("|")).explode("_tp")
    t2 = ks.groupby(by).agg(_ntext=("text_id", "nunique"), _topics=("_tp", lambda x: x[x.fillna("") != ""].nunique()))
    t = t.join(t2, how="left")
    t = t.reindex(o.index).fillna(0)
    o[f"{p}_n_kpis"] = t._n; o[f"{p}_n_esg_kpis_strict"] = t._s1; o[f"{p}_n_esg_kpis_extended"] = t._x1; o[f"{p}_n_unknown_kpis"] = t._su
    ex, lb, ub, cov = share_block(t._s1, t._su, t._n)
    o[f"{p}_esg_kpi_share_strict"] = ex; o[f"{p}_esg_kpi_share_lb"] = lb; o[f"{p}_esg_kpi_share_ub"] = ub; o[f"{p}_kpi_classification_coverage"] = cov
    ex, lb, ub, _ = share_block(t._x1, t._xu, t._n)
    o[f"{p}_esg_kpi_share_extended"] = ex; o[f"{p}_esg_kpi_ext_share_lb"] = lb; o[f"{p}_esg_kpi_ext_share_ub"] = ub
    with np.errstate(divide="ignore", invalid="ignore"):
        for q, col in [("e", "_e1"), ("s", "_sS1"), ("g", "_g1")]:
            o[f"{p}_{q}_kpi_share"] = np.where((t._n > 0) & (t._su == 0), t[col] / t._n, np.nan)
    o[f"{p}_esg_metric_count"] = t._ntext
    o[f"{p}_esg_metric_diversity"] = t._topics
    o[f"{p}_esg_e_s_g_diversity"] = (t._e1 > 0).astype(int) + (t._sS1 > 0).astype(int) + (t._g1 > 0).astype(int)
    o[f"{p}_classification_coverage"] = o[f"{p}_all_classification_coverage"]
    o[f"{p}_perf_classification_coverage"] = o[f"{p}_perf_classification_coverage"]
    o[f"{p}_esg_perf_share_lb"] = o[f"{p}_esg_perf_share_lb"]
    o[f"{p}_esg_perf_share_ub"] = o[f"{p}_esg_perf_share_ub"]
    o[f"{p}_esg_measurement_complete"] = np.where(o[f"{p}_n_perf_grants"] > 0, (o[f"{p}_n_perf_unknown_grants"] == 0).astype(float), np.nan)
    return o.reset_index()


def check_aggregate(df, p, log, name):
    """Reconciliation and range checks shared by D/E/F/G."""
    assert (df[f"{p}_n_esg_grants_strict"] + df[f"{p}_n_unknown_grants"] <= df[f"{p}_n_grants"]).all()
    assert (df[f"{p}_n_perf_grants"] <= df[f"{p}_n_grants"]).all()
    assert (df[f"{p}_n_esg_kpis_strict"] + df[f"{p}_n_unknown_kpis"] <= df[f"{p}_n_kpis"]).all()
    lbub = [(f"{p}_esg_perf_share_lb", f"{p}_esg_perf_share_ub"), (f"{p}_esg_all_share_lb", f"{p}_esg_all_share_ub"),
            (f"{p}_esg_kpi_share_lb", f"{p}_esg_kpi_share_ub")]
    for a, b in lbub:
        assert (df[a].isna() | (df[a] <= df[b] + 1e-12)).all(), f"{a} > {b}"
    for c in [c for c in df.columns if ("share" in c or "coverage" in c)]:
        s = df[c].dropna(); assert ((s >= -1e-12) & (s <= 1 + 1e-12)).all(), c
    # adoption consistent with share
    m = df[f"{p}_esg_perf_grant_share_strict"].notna()
    assert ((df.loc[m, f"{p}_esg_perf_grant_share_strict"] > 0) == (df.loc[m, f"{p}_perf_esg_adopt_strict"] == 1)).all()
    log.info(f"[aggregate checks] {name}: counts, bounds, [0,1] ranges, adoption/share consistency passed")
