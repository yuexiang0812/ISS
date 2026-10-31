"""Common aggregation of grants and KPIs to any unit (executive-year, CEO-year, firm-year, non-CEO firm-year).

中文说明：高管、CEO、公司、非 CEO 四个层级共用同一套指标定义（保证分子分母口径一致）。
所有“占比”都遵循同一规则：只有当分母中没有未分类单元时才给出精确值；同时总是给出下界 _lb（未知按 0）、上界 _ub（未知按 1）
和覆盖率。v1.1 修正：E/S/G 采用在“所有业绩型 grant 该维度均为 0”时记 0（v1.0 错误地要求所有 grant 都非 ESG）；
E/S/G 占比不再把下界当精确值发布；价值占比使用含现金激励目标支付额的合并价值；新增现金激励 / 股权业绩型 grant 拆分。

Definitions (identical at every level; prefix p = exec / ceo / firm / nonceo):
  Universe ALL      = all grants of the unit (time-based grants without performance conditions are reliably non-ESG).
  Universe PERF     = performance-vesting grants (performancetype Abs/Rel/AbsRel); split into PERF_CASH (cash incentive
                      awards: cashShort/cashLong/unitCash) and PERF_EQUITY (stock-like or option-like awards).
  Adoption          = 1 if >=1 grant in universe has ESG=1; 0 if all grants ESG=0; . otherwise / if universe empty.
  Pillar adoption   = 1 if >=1 perf grant has pillar=1; 0 if every perf grant has pillar=0; . otherwise.
  Grant share       = #ESG grants / #grants in universe, published only if no grant is unresolved;
                      _lb = #ESG / N, _ub = (#ESG + #unknown) / N, coverage = #known / N.
  Pillar grant share= same rule with pillar labels (exact only if every perf grant's pillar label is known).
  KPI share         = distinct ESG KPIs / distinct KPIs; distinct KPI = (goal_source, text_id) within the unit, i.e. the same
                      metric text used in several grants of the unit is counted once.
  Value share       = value of grants containing >=1 Strict ESG condition / value of all grants with a reported value, where
                      value = grant-date fair value, or (cash awards) the non-equity target payout. This is EXPOSURE, not value
                      attributable to ESG: KPI weights are not reliably observable (percentVest is per measurement period and
                      interacts with AND/OR groupings), so no weights are fabricated.
"""
import numpy as np, pandas as pd
from dtautil import share_block

CASH_TYPES = {"cash_incentive"}
EQUITY_TYPES = {"stock_like", "option_like"}


def _tri(n_pos, n_zero, n):
    return np.where(n_pos > 0, 1.0, np.where((n > 0) & (n_zero == n), 0.0, np.nan))


def aggregate(C, K, by, p):
    """C: grant table with `by` columns; K: KPI table with grantid (by-columns are re-attached from C)."""
    perf = C.grant_is_perf.eq(1)
    gt = C.grant_type if "grant_type" in C.columns else pd.Series("", index=C.index)
    val = C.grant_value_combined if "grant_value_combined" in C.columns else C.grant_value
    g = C.assign(
        _n=1, _perf=perf, _pcash=perf & gt.isin(CASH_TYPES), _peq=perf & gt.isin(EQUITY_TYPES),
        _s1=C.grant_esg_strict.eq(1), _s0=C.grant_esg_strict.eq(0), _su=C.grant_esg_strict.isna(),
        _x1=C.grant_esg_extended.eq(1), _x0=C.grant_esg_extended.eq(0), _xu=C.grant_esg_extended.isna(),
        _iss=C.grant_iss_esg_diag.eq(1), _accel=C.grant_time_with_acceleration.eq(1), _hasval=val.notna(), _val=val.fillna(0))
    for q in "esg":   # pillar counts use the '_pil' prefix: '_s1p' is reserved for Strict (v1.1 fix of a name collision)
        g[f"_pil{q}1"] = C[f"grant_esg_{q}"].eq(1) & perf
        g[f"_pil{q}0"] = C[f"grant_esg_{q}"].eq(0) & perf
        g[f"_pil{q}u"] = C[f"grant_esg_{q}"].isna() & perf
    for f in ["_s1", "_s0", "_su", "_x1", "_x0", "_xu"]:
        g[f + "p"] = g[f] & g._perf
        g[f + "c"] = g[f] & g._pcash
        g[f + "q"] = g[f] & g._peq
    g["_val_esg"] = np.where(g._s1, g._val, 0.0)
    g["_valp"] = np.where(g._perf, g._val, 0.0)
    g["_val_esgp"] = np.where(g._s1 & g._perf, g._val, 0.0)
    cols = [c for c in g.columns if c.startswith("_") and c not in ("_val",)] + ["_val"]
    assert len(cols) == len(set(cols)), "duplicate helper column names"
    s = g.groupby(by)[cols].sum()
    o = pd.DataFrame(index=s.index)
    o[f"{p}_n_grants"] = s._n; o[f"{p}_n_perf_grants"] = s._perf; o[f"{p}_n_time_accel_grants"] = s._accel
    o[f"{p}_n_perf_cash_grants"] = s._pcash; o[f"{p}_n_perf_equity_grants"] = s._peq
    o[f"{p}_n_esg_grants_strict"] = s._s1; o[f"{p}_n_esg_grants_extended"] = s._x1; o[f"{p}_n_unknown_grants"] = s._su
    o[f"{p}_n_unknown_grants_ext"] = s._xu
    o[f"{p}_n_perf_esg_grants_strict"] = s._s1p; o[f"{p}_n_perf_esg_grants_extended"] = s._x1p; o[f"{p}_n_perf_unknown_grants"] = s._sup
    o[f"{p}_esg_adopt_strict"] = _tri(s._s1, s._s0, s._n)
    o[f"{p}_esg_adopt_extended"] = _tri(s._x1, s._x0, s._n)
    o[f"{p}_perf_esg_adopt_strict"] = _tri(s._s1p, s._s0p, s._perf)
    o[f"{p}_perf_esg_adopt_extended"] = _tri(s._x1p, s._x0p, s._perf)
    o[f"{p}_perf_cash_esg_adopt_strict"] = _tri(s._s1c, s._s0c, s._pcash)
    o[f"{p}_perf_equity_esg_adopt_strict"] = _tri(s._s1q, s._s0q, s._peq)
    for q in "esg":
        o[f"{p}_esg_{q}_adopt"] = _tri(s[f"_pil{q}1"], s[f"_pil{q}0"], s._perf)      # v1.1 fix (pillar-specific zero condition)
    for univ, npos, nunk, ntot in [("all", "_s1", "_su", "_n"), ("perf", "_s1p", "_sup", "_perf"),
                                   ("perf_cash", "_s1c", "_suc", "_pcash"), ("perf_equity", "_s1q", "_suq", "_peq")]:
        ex, lb, ub, cov = share_block(s[npos], s[nunk], s[ntot])
        o[f"{p}_esg_{univ}_grant_share_strict"] = ex; o[f"{p}_esg_{univ}_share_lb"] = lb; o[f"{p}_esg_{univ}_share_ub"] = ub
        if univ in ("all", "perf"):
            o[f"{p}_{univ}_classification_coverage"] = cov
    for univ, npos, nunk, ntot in [("all", "_x1", "_xu", "_n"), ("perf", "_x1p", "_xup", "_perf")]:
        ex, lb, ub, _ = share_block(s[npos], s[nunk], s[ntot])
        o[f"{p}_esg_{univ}_grant_share_extended"] = ex; o[f"{p}_esg_{univ}_ext_share_lb"] = lb; o[f"{p}_esg_{univ}_ext_share_ub"] = ub
    for q in "esg":
        ex, lb, ub, _ = share_block(s[f"_pil{q}1"], s[f"_pil{q}u"], s._perf)
        o[f"{p}_{q}_grant_share"] = ex; o[f"{p}_{q}_grant_share_lb"] = lb; o[f"{p}_{q}_grant_share_ub"] = ub
    with np.errstate(divide="ignore", invalid="ignore"):
        o[f"{p}_total_grant_value"] = np.where(s._hasval > 0, s._val, np.nan)
        o[f"{p}_esg_compensation_value_share"] = np.where(s._val > 0, s._val_esg / s._val, np.nan)
        o[f"{p}_perf_esg_compensation_value_share"] = np.where(s._valp > 0, s._val_esgp / s._valp, np.nan)
        o[f"{p}_value_coverage"] = np.where(s._n > 0, s._hasval / s._n, np.nan)
    o[f"{p}_iss_esg_adopt_diag"] = np.where(s._n > 0, (s._iss > 0).astype(float), np.nan)

    # ---- KPI level (distinct KPI = (goal_source, text_id) within unit)
    kk = K.drop(columns=[c for c in by if c in K.columns]).merge(C[["grantid"] + by], on="grantid", how="inner")
    kk = kk.drop_duplicates(by + ["goal_source", "text_id"])
    kk = kk.assign(_n=1, _s1=kk.kpi_esg_strict.eq(1), _su=kk.kpi_esg_strict.isna(), _x1=kk.kpi_esg_extended.eq(1),
                   _xu=kk.kpi_esg_extended.isna(),
                   _e1=kk.kpi_esg_e.eq(1), _eu=kk.kpi_esg_e.isna(), _sS1=kk.kpi_esg_s.eq(1), _sSu=kk.kpi_esg_s.isna(),
                   _g1=kk.kpi_esg_g.eq(1), _gu=kk.kpi_esg_g.isna())
    t = kk.groupby(by)[["_n", "_s1", "_su", "_x1", "_xu", "_e1", "_eu", "_sS1", "_sSu", "_g1", "_gu"]].sum()
    ks = kk[kk._s1].assign(_tp=kk.loc[kk._s1, "esg_topics_strict"].str.split("|")).explode("_tp")
    t2 = ks.groupby(by).agg(_ntext=("text_id", "nunique"), _topics=("_tp", lambda x: x[x.fillna("") != ""].nunique()),
                            _ids=("text_id", lambda x: "|".join(sorted(set(x)))))
    t = t.join(t2, how="left")
    t = t.reindex(o.index)
    num = [c for c in t.columns if c != "_ids"]
    t[num] = t[num].fillna(0); t["_ids"] = t["_ids"].fillna("")
    o[f"{p}_n_kpis"] = t._n; o[f"{p}_n_esg_kpis_strict"] = t._s1; o[f"{p}_n_esg_kpis_extended"] = t._x1; o[f"{p}_n_unknown_kpis"] = t._su
    ex, lb, ub, cov = share_block(t._s1, t._su, t._n)
    o[f"{p}_esg_kpi_share_strict"] = ex; o[f"{p}_esg_kpi_share_lb"] = lb; o[f"{p}_esg_kpi_share_ub"] = ub; o[f"{p}_kpi_classification_coverage"] = cov
    ex, lb, ub, _ = share_block(t._x1, t._xu, t._n)
    o[f"{p}_esg_kpi_share_extended"] = ex; o[f"{p}_esg_kpi_ext_share_lb"] = lb; o[f"{p}_esg_kpi_ext_share_ub"] = ub
    for q, c1, cu in [("e", "_e1", "_eu"), ("s", "_sS1", "_sSu"), ("g", "_g1", "_gu")]:
        ex, lb, ub, _ = share_block(t[c1], t[cu], t._n)
        o[f"{p}_{q}_kpi_share"] = ex; o[f"{p}_{q}_kpi_share_lb"] = lb; o[f"{p}_{q}_kpi_share_ub"] = ub
    o[f"{p}_esg_metric_count"] = t._ntext
    o[f"{p}_esg_metric_diversity"] = t._topics
    o[f"{p}_esg_e_s_g_diversity"] = (t._e1 > 0).astype(int) + (t._sS1 > 0).astype(int) + (t._g1 > 0).astype(int)
    o[f"{p}_esg_text_ids"] = t._ids
    o[f"{p}_classification_coverage"] = o[f"{p}_all_classification_coverage"]
    o[f"{p}_esg_measurement_complete"] = np.where(o[f"{p}_n_perf_grants"] > 0, (o[f"{p}_n_perf_unknown_grants"] == 0).astype(float), np.nan)
    return o.reset_index()


COUNT_PREFIXES = ("_n_",)


def fill_counts(df, p):
    """Units without grants: counts are 0 (not missing); measures stay missing (= not applicable)."""
    for c in df.columns:
        if c.startswith(f"{p}_n_") or c in (f"{p}_esg_metric_count", f"{p}_esg_metric_diversity", f"{p}_esg_e_s_g_diversity"):
            df[c] = df[c].fillna(0)
    if f"{p}_esg_text_ids" in df.columns:
        df[f"{p}_esg_text_ids"] = df[f"{p}_esg_text_ids"].fillna("")
    return df


def check_aggregate(df, p, log, name):
    """Reconciliation and range checks shared by D/E/F/G."""
    assert (df[f"{p}_n_esg_grants_strict"] + df[f"{p}_n_unknown_grants"] <= df[f"{p}_n_grants"]).all()
    assert (df[f"{p}_n_perf_grants"] <= df[f"{p}_n_grants"]).all()
    assert (df[f"{p}_n_perf_cash_grants"] + df[f"{p}_n_perf_equity_grants"] <= df[f"{p}_n_perf_grants"]).all()
    assert (df[f"{p}_n_esg_kpis_strict"] + df[f"{p}_n_unknown_kpis"] <= df[f"{p}_n_kpis"]).all()
    pairs = [(c, c[:-2] + "ub") for c in df.columns if c.endswith("_lb") and c[:-2] + "ub" in df.columns]
    for a, b in pairs:
        assert (df[a].isna() | (df[a] <= df[b] + 1e-12)).all(), f"{a} > {b}"
    for c in [c for c in df.columns if ("share" in c or "coverage" in c) and df[c].dtype.kind == "f"]:
        s = df[c].dropna(); assert ((s >= -1e-12) & (s <= 1 + 1e-12)).all(), c
    # exact share, when published, lies inside [lb, ub] and equals lb
    for ex, lb in [(f"{p}_esg_perf_grant_share_strict", f"{p}_esg_perf_share_lb"), (f"{p}_e_grant_share", f"{p}_e_grant_share_lb"),
                   (f"{p}_esg_kpi_share_strict", f"{p}_esg_kpi_share_lb")]:
        m = df[ex].notna()
        assert np.allclose(df.loc[m, ex], df.loc[m, lb]), f"{ex} != {lb} where exact"
    m = df[f"{p}_esg_perf_grant_share_strict"].notna()
    assert ((df.loc[m, f"{p}_esg_perf_grant_share_strict"] > 0) == (df.loc[m, f"{p}_perf_esg_adopt_strict"] == 1)).all()
    # pillar adoption cannot be 1 unless Strict adoption among perf grants is 1
    for q in "esg":
        assert not ((df[f"{p}_esg_{q}_adopt"] == 1) & (df[f"{p}_perf_esg_adopt_strict"] != 1)).any(), q
    log.info(f"[aggregate checks] {name}: counts, cash+equity<=perf, lb<=ub ({len(pairs)} pairs), [0,1] ranges, exact=lb, "
             f"adoption/share and pillar/strict consistency passed")
