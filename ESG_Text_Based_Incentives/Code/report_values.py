"""Numbers, tables and narrative checks for the auto-generated reports (Step 18).

中文说明：从当前流水线输出（CSV / parquet / JSON）读取报告所需的全部数字与表格——报告里不手写任何数字。
同时逐条检查报告中的叙述性结论（如“2018 年跳升来自 ISS 改分类”）是否仍被当前数据支持；不支持时，
报告顶部会显示警告，日志也会提示，必须人工修改模板中的叙述后才能对外使用。
"""
import json, re, datetime as dt, subprocess
import numpy as np, pandas as pd, pyarrow.parquet as pq
from config import (PROJ, DOCS, VALID, INTER, DICT, ANNUAL, CLASSIFIER_VERSION as VER, PREVIOUS_VERSION as PREV,
                    SAMPLE_VERSION, STATS_FILE)
from esg_rules import R

REPO = PROJ.parent


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO).stdout.strip()


def num(x):
    return "n/a" if x is None or pd.isna(x) else f"{int(round(float(x))):,}"


def pct(x, d=1):
    return "n/a" if x is None or pd.isna(x) else f"{100 * float(x):.{d}f}%"


def pp(x, d=1):
    return "n/a" if x is None or pd.isna(x) else f"{100 * float(x):+.{d}f} pp"


def md(df):
    """DataFrame -> GitHub markdown table (all cells as given)."""
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.astype(object).where(df.notna(), "").itertuples(index=False):
        out.append("| " + " | ".join(str(v).replace("|", "/") for v in r) + " |")
    return "\n".join(out)


def nrows(path):
    return pq.ParquetFile(path).metadata.num_rows


class Values:
    """V: scalar strings; T: markdown tables; F: DataFrames (for docx tables); checks: narrative checks."""

    def __init__(self):
        self.V, self.T, self.F, self.checks = {}, {}, {}, []

    def claim(self, ok, text):
        self.checks.append(dict(ok=bool(ok), claim=text))

    def table(self, name, df):
        self.F[name] = df
        self.T[name] = md(df)


def collect():
    X = Values(); V, claim = X.V, X.claim
    V.update(version=VER, prev_version=PREV, sample_version=SAMPLE_VERSION, generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
             commit=sh("git rev-parse --short HEAD") or "n/a", n_rules=str(len(R)))
    stats = json.loads(STATS_FILE.read_text()) if STATS_FILE.exists() else {}
    st = lambda step, key: stats.get(step, {}).get(key)

    # ------------------------------------------------------------------ validation status
    vs = json.loads((VALID / f"validation_status_{VER}.json").read_text())
    ids = pd.read_csv(VALID / f"validation_sample_{SAMPLE_VERSION}_ids.csv")
    V["valid_n"], V["valid_strata"] = num(len(ids)), num(ids.stratum.nunique())
    if vs["status"] == "validated_against_human_labels":
        M = pd.read_csv(VALID / f"validation_metrics_{VER}.csv")
        m = M[(M.classifier_version == VER) & (M.dimension == "esg_strict") & (M.group == "all") & (M.weight == "w_unit")].set_index("metric")
        f = lambda k: f"{m.loc[k, 'estimate']:.3f} [{m.loc[k, 'ci_low']:.3f}, {m.loc[k, 'ci_high']:.3f}]"
        V["validation_label"] = "VALIDATED AGAINST ADJUDICATED HUMAN LABELS"
        V["validation_en"] = (f"{vs['n_labelled']} sample units carry adjudicated human labels. Strict ESG (unit-weighted, 95% CI): "
                              f"precision {f('precision')}, recall {f('recall')}, F1 {f('f1')}; full results in "
                              f"`Validation/validation_metrics_{VER}.csv`.")
        V["validation_cn"] = (f"已完成：{vs['n_labelled']} 个样本单元有裁定后的人工标签。Strict ESG（按单元加权，95% 置信区间）："
                              f"精确率 {f('precision')}，召回率 {f('recall')}，F1 {f('f1')}。")
    else:
        V["validation_label"] = "PROVISIONAL"
        V["validation_en"] = (f"Every label comes from the deterministic classifier {VER}. No adjudicated human reference labels exist yet, "
                              f"so **no accuracy statistic is reported**. The blind validation sample ({V['valid_n']} units, frozen under "
                              f"{SAMPLE_VERSION}), the coding guideline and the scoring code are ready (§12).")
        V["validation_cn"] = (f"尚未完成。在人工标注返回之前，所有标签都是暂定（Provisional），不报告任何准确率。"
                              f"{V['valid_n']} 个单元的盲编码样本、编码手册与评分程序均已就绪。")

    # ------------------------------------------------------------------ inventory and raw-data facts
    inv = pd.read_csv(DOCS / "data_inventory_files.csv").set_index("file")
    fld = pd.read_csv(DOCS / "data_inventory_fields.csv")
    C = pd.read_parquet(INTER / "dataset_C.parquet", columns=[
        "grant_dup_resolved", "participant_matched", "grant_is_hybrid_absrel", "grant_goal_status", "grant_goal_data_incomplete",
        "grant_value_source", "grant_date_suspect", "grant_dates_inconsistent"])
    gfile = [f for f in inv.index if f.startswith("08.")][0]
    roles = [("08.", "grants, award attributes, performance type"), ("02.", "goal text and payout (absolute goals)"),
             ("16.", "goal text and peer benchmark (relative goals)"), ("03.", "acceleration conditions"),
             ("12.", "identity, title, role codes, currentCEO"), ("05.", "firm-year universe, name, ticker, CUSIP")]
    rows = []
    for pre, role in roles:
        f = [x for x in inv.index if x.startswith(pre)][0]
        r = num(inv.loc[f, "rows"]) + (f" ({num(len(C))} distinct grantID)" if pre == "08." else "")
        rows.append([f.replace(".dta", ""), role, r])
    X.table("inventory", pd.DataFrame(rows, columns=["File", "Role", "Rows"]))
    fv = lambda field, col: fld[(fld.file == gfile) & (fld.field == field)][col].iloc[0]
    V.update(n_fv_missing_code=num(fv("grantDateFV", "n_missing_code_le_-9999")), n_net_missing_code=num(fv("nonEquityTarget", "n_missing_code_le_-9999")),
             n_grantdate_missing_code=num(fv("grantDate", "n_missing_date_code")),
             n_neg_fv=num(st("08", "n_negative_grantdatefv")), n_neg_vest=num(st("08", "n_negative_vesthighgrant")),
             fy_match_share=pct(st("03", "goal_fy_equals_grant_fy_share"), 4))
    absf = [x for x in inv.index if x.startswith("02.")][0]; pfy = [x for x in inv.index if x.startswith("12.")][0]
    V.update(dup_absid=num(inv.loc[absf, "dup_absId"]), dup_absid_period=num(inv.loc[absf, "dup_absId+periodID"]),
             dup_pfy_3key=num(inv.loc[pfy, "dup_CIK+FiscalYear+participantid"]))
    n_dup_ids = int(C.grant_dup_resolved.sum()); surplus = int(inv.loc[gfile, "rows"]) - len(C)
    V.update(n_dup_grant_ids=num(n_dup_ids), n_dup_grant_surplus=num(surplus), n_dup_grant_rows=num(n_dup_ids + surplus))

    GR = pd.read_parquet(INTER / "goal_records.parquet", columns=["fiscalYear", "metric", "goal_grant_matched", "grantId"])
    from config import ISS_2018_ESG_METRIC_LABELS
    lab = GR.metric.isin(ISS_2018_ESG_METRIC_LABELS)
    V.update(n_goal_records=num(len(GR)), n_esg_label_rows=num(lab.sum()), n_esg_label_pre2018=num((lab & (GR.fiscalYear < 2018)).sum()),
             goal_match_share=pct(GR.goal_grant_matched.mean(), 4), n_goal_unmatched=num((GR.goal_grant_matched == 0).sum()),
             n_goal_unmatched_grants=num(GR.loc[GR.goal_grant_matched == 0, "grantId"].nunique()))
    claim(int((lab & (GR.fiscalYear < 2018)).sum()) < 0.02 * max(int(lab.sum()), 1),
          "ISS ESG `metric` labels are (almost) absent before 2018 (part of the 2018 re-taxonomy)")
    del GR
    cov = pd.read_csv(ANNUAL / "annual_text_coverage.csv").set_index("fiscalYear")
    for y in (1998, 2010, 2018, 2021):
        V[f"blank_{y}"] = pct(cov.loc[y, "metricother_blank_share"], 0)
    V.update(grant_pfy_match_share=pct(C.participant_matched.mean(), 3), n_grant_pfy_unmatched=num((C.participant_matched == 0).sum()),
             n_hybrid=num(C.grant_is_hybrid_absrel.sum()), n_goal_incomplete=num(C.grant_goal_data_incomplete.sum()),
             n_date_suspect=num(C.grant_date_suspect.sum()), n_date_inconsistent=num(C.grant_dates_inconsistent.sum()))
    vsrc = C.grant_value_source.value_counts()
    V["value_source_counts"] = "; ".join(f"{k.replace('_', ' ')} {num(v)}" for k, v in vsrc.items())
    desc = {"perf_with_goals": "performance grant with goal records", "perf_goals_missing": "performance grant, goal data missing (missing data ≠ no condition)",
            "time_no_perf_condition": "time grant (reliably no ESG condition)", "time_with_accel_goals": "time grant with acceleration goals",
            "time_accel_declared_goals_missing": "time grant, acceleration declared, goals missing", "type_missing": "performance type missing"}
    gs = C.grant_goal_status.value_counts()
    X.table("goal_status", pd.DataFrame([[k, desc.get(k, ""), num(v)] for k, v in gs.items()], columns=["Status", "Meaning", "Grants"]))
    del C

    # ------------------------------------------------------------------ KPI, units, firm-years
    B = pd.read_parquet(INTER / "dataset_B.parquet", columns=["n_periods", "kpi_duplicate_flag", "kpi_source_count"])
    V.update(n_kpis=num(len(B)), n_kpi_multiperiod=num((B.n_periods > 1).sum()), n_kpi_dupobj=num(B.kpi_duplicate_flag.sum()),
             n_kpi_source_rows=num(B.kpi_source_count.sum()))
    del B
    A = pd.read_parquet(INTER / "dataset_A.parquet", columns=["classification_method", "n_goal_rows", "review_flags", "esg_strict"])
    V.update(n_units=num(len(A)), n_rows_structured=num(A.loc[A.classification_method == "structured_context", "n_goal_rows"].sum()),
             n_esg_under_fin=num(A.review_flags.str.contains("esg_term_under_financial_label").sum()),
             unknown_unit_share=pct(A.esg_strict.isna().mean()))
    F = pd.read_parquet(INTER / "dataset_F.parquet", columns=["firm_has_grants"])
    V["n_fy_no_grants"] = num((F.firm_has_grants == 0).sum())

    # ------------------------------------------------------------------ CEO
    cs = pd.read_parquet(INTER / "ceo_status_firmyear.parquet").ceo_identification_status.value_counts()
    treat = {"unique_current_ceo_flag": "strict CEO sample (`ceo_strict_sample = 1`)",
             "multiple_current_ceo_flags": "all candidates kept; none silently selected; in exception table",
             "rolecode_fallback_unique": "kept as an alternative (not strict)", "rolecode_ambiguous": "exception table only",
             "no_ceo_identified": "exception table only"}
    X.table("ceo_status", pd.DataFrame([[k, num(v), treat.get(k, "")] for k, v in cs.items()], columns=["Status", "Firm-years", "Treatment"]))
    ex = pd.read_csv(INTER / "audit_ceo_exceptions.csv", usecols=["cik", "fiscalyear"])
    G = pd.read_parquet(INTER / "dataset_G.parquet", columns=["nonceo_n_executives", "nonceo_n_role_unknown_execs"])
    V.update(n_ceo_exc_rows=num(len(ex)), n_ceo_exc_fy=num(len(ex.drop_duplicates())), n_nonceo_execyears=num(G.nonceo_n_executives.sum()),
             n_role_unknown=num(st("11", "n_role_unknown")), n_role_unknown_in_g=num(G.nonceo_n_role_unknown_execs.sum()))

    # ------------------------------------------------------------------ dictionary deliverables
    rules = pd.read_csv(DICT / f"b_revised_rules_{VER}.csv")
    V["rule_kinds"] = ", ".join(f"{k} {v}" for k, v in rules.kind.value_counts().items())
    kw = pd.read_csv(DICT / f"b_paper_keyword_review_{VER}.csv").decision.value_counts()
    X.table("keyword_review", pd.DataFrame([[k.replace("_", " "), num(v)] for k, v in kw.items()], columns=["Decision", "Keywords"]))
    V["n_new_expr"] = num(len(pd.read_csv(DICT / f"b_new_expressions_{VER}.csv")))

    # ------------------------------------------------------------------ AGHJ comparison and replication
    ov = pd.read_csv(VALID / "e_overlap_strict_goal_rows.csv").set_index("paper")
    X.table("overlap_rows", pd.DataFrame(
        [[f"AGHJ = {r[-1]} ({num(ov.loc[r, 'All'])} rows)", num(ov.loc[r, "rev_strict=1"]), num(ov.loc[r, "rev_strict=0"]), num(ov.loc[r, "rev_strict=Unknown"])]
         for r in ("paper=1", "paper=0")], columns=["", f"{VER} Strict = 1", f"{VER} Strict = 0", f"{VER} Unknown"]))
    V["n_paper_pos_not_strict"] = num(ov.loc["paper=1", "rev_strict=0"] + ov.loc["paper=1", "rev_strict=Unknown"])
    dc = pd.read_csv(VALID / "e_disagreement_categories.csv").set_index("cat")
    names = {"paper_esg_rev_extended_only": "Extended-only (customer retention, SAIDI, patient satisfaction …)",
             "paper_esg_rev_adjacent_excluded": "ESG-adjacent by definition (regulatory compliance, succession, culture …)",
             "paper_esg_rev_unknown": "Unknown, no adjacent flag (e.g. 'Leadership', 'Integrity', 'Energy efficiency')",
             "paper_esg_rev_non_esg": "Generic or false positive (cost/debt 'reduction', 'policies in force', company names …)"}
    X.table("disagreement", pd.DataFrame([[v, num(dc.loc[k, "units"]), num(dc.loc[k, "goal_rows"])] for k, v in names.items()],
                                         columns=["Category", "Units", "Goal rows"]))
    V.update(n_rev_only_units=num(dc.loc["paper_non_esg_rev_strict", "units"]), n_rev_only_rows=num(dc.loc["paper_non_esg_rev_strict", "goal_rows"]))
    rb = pd.read_csv(VALID / "e_paper_replication_benchmark.csv")
    X.table("replication", pd.DataFrame({"FY": rb.fiscalyear.astype(int), "Executive-years (ours)": rb.n_obs.map(num),
                                         "AGHJ method, our data": rb.our_paper_dictionary_pct.map(lambda v: f"{v:.1f}%"),
                                         "AGHJ Table 1 (published)": rb.aghj_2025_table1_pct.map(lambda v: f"{v:.1f}%"),
                                         f"{VER} Strict lb, our data": rb.our_v_strict_lb_pct.map(lambda v: f"{v:.1f}%")}))
    close = rb[(rb.our_paper_dictionary_pct - rb.aghj_2025_table1_pct).abs() <= 3].fiscalyear.astype(int).tolist()
    V["replication_close_years"] = ", ".join(map(str, close))
    if "aghj_2025_table1_n" in rb.columns:
        pre = rb[rb.fiscalyear < 2018].aghj_2025_table1_n
        V["aghj_n_range_pre2018"] = f"{num(pre.min())}–{num(pre.max())}"
    else:
        V["aghj_n_range_pre2018"] = "n/a"

    # ------------------------------------------------------------------ coverage, datasets, variables, audit
    sel = [1998, 2003, 2008, 2013, 2017, 2018, 2021]
    X.table("text_coverage", pd.DataFrame({"Year": sel, "Goal rows": [num(cov.loc[y, "goal_rows"]) for y in sel],
                                           "metricOther blank": [pct(cov.loc[y, "metricother_blank_share"], 0) for y in sel],
                                           f"{VER} Strict Unknown share": [pct(cov.loc[y, "unknown_share"], 0) for y in sel],
                                           "ISS ESG share (diag)": [pct(cov.loc[y, "iss_esg_share_diag"]) for y in sel]}))
    V["n_variables"] = num(len(pd.read_csv(DOCS / "variable_dictionary.csv")))
    ds = pd.read_csv(DOCS / "dataset_summary.csv")
    tag = {"ESG_Text_Dictionary.dta": "A", "ESG_KPI_Master.dta": "B", "ESG_Goal_Record_Classification.dta": "(B-alt)", "ESG_Grant_Master.dta": "C",
           "ESG_Executive_Firm_Year.dta": "D", "ESG_CEO_Firm_Year.dta": "E", "ESG_Firm_Year_Master.dta": "F", "ESG_NonCEO_Firm_Year.dta": "G"}
    order = ["ESG_Text_Dictionary.dta", "ESG_KPI_Master.dta", "ESG_Goal_Record_Classification.dta", "ESG_Grant_Master.dta",
             "ESG_Executive_Firm_Year.dta", "ESG_CEO_Firm_Year.dta", "ESG_Firm_Year_Master.dta", "ESG_NonCEO_Firm_Year.dta"]
    ds = ds.set_index("dataset").loc[[d for d in order if d in set(ds.dataset)]].reset_index()
    X.table("datasets", pd.DataFrame({"Dataset": [f"{tag[d]} `{d}`" for d in ds.dataset], "Obs": ds.observations.map(num),
                                      "Vars": ds.variables, "Primary key": ds.primary_key.str.replace("+", " + "),
                                      "Years": [f"{int(a)}–{int(b)}" for a, b in zip(ds.year_min, ds.year_max)]}))
    Q = pd.read_csv(DOCS / "quality_audit_results.csv"); qc = Q.status.value_counts()
    V["audit_summary"] = f"{len(Q)} checks: PASS {qc.get('PASS', 0)}, FAIL {qc.get('FAIL', 0)}, WARN {qc.get('WARN', 0)}, INFO {qc.get('INFO', 0)}"
    claim(qc.get("FAIL", 0) == 0, "the independent quality audit has no FAIL")
    X.table("reconciliation", pd.DataFrame([
        ["Goal records → grant", f"{V['goal_match_share']} matched ({V['n_goal_unmatched']} records, {V['n_goal_unmatched_grants']} grants unmatched)"],
        ["Grants → ParticipantFY (exact 4 keys)", f"{V['grant_pfy_match_share']} matched ({V['n_grant_pfy_unmatched']} unmatched)"],
        ["Grants → CompanyFY firm-year", "100% (asserted)"],
        ["Σ KPI source rows = goal records", f"{V['n_kpi_source_rows']} = {V['n_goal_records']}"],
        ["Σ grant KPIs = KPI master (matched grants); esg + non-esg + unknown = n_kpis per grant", "asserted"],
        ["Σ executive grants = Σ firm grants = grant master", num(ds.loc[ds.dataset == "ESG_Grant_Master.dta", "observations"].iloc[0])],
        ["Firm ESG / perf / all grant counts = Σ over executive-years", "asserted for every firm-year"],
        ["Shares in [0,1]; lb ≤ ub; exact = lb when complete; cash + equity ≤ perf; pillar adoption ⇒ Strict adoption", "asserted (Steps 08–11) and re-checked (Step 16)"],
        ["Strict = 1 ⇒ Extended = 1", "asserted; 0 violations"]], columns=["Check", "Result"]))

    # ------------------------------------------------------------------ annual results
    fy = pd.read_csv(ANNUAL / "annual_firm_year.csv").set_index("fiscalyear")
    ex_ = pd.read_csv(ANNUAL / "annual_executive_year.csv").set_index("fiscalyear")
    ce = pd.read_csv(ANNUAL / "annual_ceo_year_strict_sample.csv").set_index("fiscalyear")
    for y in (2015, 2017, 2018, 2020, 2021):
        V[f"lb_{y}"], V[f"iss_{y}"] = pct(fy.loc[y, "adopt_strict_lb"]), pct(fy.loc[y, "iss_esg_adopt_diag"])
    for y in (1998, 2017, 2018, 2021):
        V[f"cov_{y}"] = f"{fy.loc[y, 'perf_classification_coverage_mean']:.2f}"
    years = [1998, 2003, 2008, 2013, 2015, 2016, 2017, 2018, 2019, 2020, 2021]
    X.table("annual_firm", pd.DataFrame({
        "FY": years, "Firms": [num(fy.loc[y, "n_units_with_perf_grants"]) for y in years],
        "Adopt lb": [pct(fy.loc[y, "adopt_strict_lb"]) for y in years], "Complete-case": [pct(fy.loc[y, "adopt_strict_cc"]) for y in years],
        "Adopt ub": [pct(fy.loc[y, "adopt_strict_ub"]) for y in years], "Extended lb": [pct(fy.loc[y, "adopt_ext_lb"]) for y in years],
        "Mean perf-grant share lb": [pct(fy.loc[y, "perf_grant_share_lb_mean"]) for y in years],
        "Mean perf coverage": [f"{fy.loc[y, 'perf_classification_coverage_mean']:.2f}" for y in years],
        "ISS ESG (diag)": [pct(fy.loc[y, "iss_esg_adopt_diag"]) for y in years]}))
    py = [2015, 2017, 2018, 2020, 2021]
    X.table("pillars", pd.DataFrame([[p] + [pct(fy.loc[y, f"adopt_{p}_lb"]) for y in py] for p in "ESG"], columns=["Pillar"] + [str(y) for y in py]))
    X.table("exec_ceo", pd.DataFrame([[y, f"{pct(ex_.loc[y, 'adopt_strict_lb'])} ({pct(ce.loc[y, 'adopt_strict_lb'])})"] for y in (2015, 2017, 2018, 2020, 2021)],
                                     columns=["Year", "Executives (CEO)"]))
    cq = pd.read_csv(ANNUAL / "annual_cash_vs_equity_firm.csv").set_index("fiscalyear")
    X.table("cash_equity", pd.DataFrame([[y, num(cq.loc[y, "firms"]), pct(cq.loc[y, "adopt_any_perf_lb"]), pct(cq.loc[y, "adopt_cash_perf_lb"]),
                                          pct(cq.loc[y, "adopt_equity_perf_lb"])] for y in (2008, 2015, 2017, 2018, 2020, 2021)],
                                        columns=["FY", "Firms with perf grants", "ESG in any perf grant", "ESG in a cash incentive award", "ESG in an equity performance award"]))
    bk = pd.read_csv(ANNUAL / "break_iss_vs_text_kpi_2014_2021.csv")
    s1 = bk.groupby("yr").text_strict1.sum()
    V["kpi_strict_2017"], V["kpi_strict_2018"] = num(s1.loc[2017]), num(s1.loc[2018])
    bt = bk.pivot_table(index="yr", columns="kpi_iss_esg_flag_diag", values=["text_strict1", "text_strict0", "text_unknown"], aggfunc="sum").fillna(0)
    rows = []
    for y in bt.index:
        g = lambda v, f: num(bt.loc[y, (v, f)]) if (v, f) in bt.columns else "0"
        rows.append([int(y), g("text_strict1", "ISS_ESG"), g("text_strict0", "ISS_ESG"), g("text_unknown", "ISS_ESG"),
                     g("text_strict1", "ISS_nonESG")])
    X.table("break_kpi", pd.DataFrame(rows, columns=["FY", "ISS-ESG KPIs: text Strict 1", "text Strict 0", "text Unknown", "ISS non-ESG KPIs: text Strict 1"]))
    comp = pd.read_csv(ANNUAL / "break_sample_composition_2017_2018.csv", index_col=0).iloc[:, 0]
    V.update(n_continuing=num(comp["continuing"]), n_exits=num(comp["exits_after_2017"]), n_entrants=num(comp["entrants_2018"]),
             cont_2017=pct(comp["continuing_2017_2018_2017_adopt_lb"]), cont_2018=pct(comp["continuing_2017_2018_2018_adopt_lb"]),
             n_balanced=num(comp["balanced_panel_2015_2021_firms"]))
    bp = pd.read_csv(ANNUAL / "break_balanced_panel_2015_2021.csv").set_index("fiscalyear")
    X.table("balanced", pd.DataFrame({"FY": bp.index.astype(int), "Adopt lb": bp.adopt_lb.map(pct), "Complete-case": bp.adopt_cc.map(pct),
                                      "Adopt ub": bp.adopt_ub.map(pct), "Unknown": bp.unknown.map(pct)}))
    dec = pd.read_csv(ANNUAL / "break_extensive_intensive_decomposition.csv").set_index("period")
    X.table("margins", pd.DataFrame({"Period": dec.index, "Δ mean share": dec.d_mean_share.map(pp), "Extensive": dec.extensive.map(pp),
                                     "Intensive": dec.intensive.map(pp)}))
    e, i = dec.loc["2018-2021", "extensive"], dec.loc["2018-2021", "intensive"]
    V["margin_sentence"] = (f"From 2018 to 2021 the mean share rises by {pp(dec.loc['2018-2021', 'd_mean_share'])}; "
                            f"{pp(e)} comes from more firms adopting (extensive margin) and {pp(i)} from higher intensity among adopters.")

    # ------------------------------------------------------------------ narrative checks (each sentence in the template that interprets numbers)
    f17, f18, f20, f21 = (fy.loc[y] for y in (2017, 2018, 2020, 2021))
    claim(f18.iss_esg_adopt_diag - f17.iss_esg_adopt_diag > 0.05 and abs(f18.adopt_strict_lb - f17.adopt_strict_lb) < 0.03,
          "2018 jump: ISS categories jump > 5 pp in 2018 while uniform text adoption (lb) moves < 3 pp")
    claim(f21.adopt_strict_lb - f20.adopt_strict_lb > 0.05 and f21.adopt_strict_lb - f17.adopt_strict_lb > 2 * abs(f18.adopt_strict_lb - f17.adopt_strict_lb),
          "the real increase is concentrated in 2020-2021")
    claim(e > abs(i), "2018-2021 increase driven by the extensive margin")
    claim(f21.adopt_S_lb > max(f21.adopt_E_lb, f21.adopt_G_lb) and (f21.adopt_S_lb - f18.adopt_S_lb) >= max(f21.adopt_E_lb - f18.adopt_E_lb, f21.adopt_G_lb - f18.adopt_G_lb),
          "Social conditions drive the level and the increase")
    claim(abs(f18.perf_classification_coverage_mean - f17.perf_classification_coverage_mean) < 0.05, "no coverage discontinuity at 2018")
    claim(abs(comp["continuing_2017_2018_2018_adopt_lb"] - comp["continuing_2017_2018_2017_adopt_lb"]) < 0.03,
          "continuing firms 2017->2018 change < 3 pp (composition is not the explanation)")
    claim(s1.loc[2018] < 1.2 * s1.loc[2017], "text-Strict KPI counts do not jump in 2018")
    claim(cq.loc[2021, "adopt_cash_perf_lb"] > 2 * cq.loc[2021, "adopt_equity_perf_lb"], "ESG conditions sit mainly in cash incentive plans")

    # ------------------------------------------------------------------ version comparison and review findings
    tagv = f"{PREV}_to_{VER}"
    ct = DOCS / f"version_comparison_{tagv}_change_types.csv"
    if ct.exists():
        ctd = pd.read_csv(ct)
        V.update(n_units_changed=num(ctd.units.sum()), n_rows_changed=num(ctd.goal_rows.sum()))
        X.table("change_types", ctd.head(12).assign(units=ctd.units.map(num), goal_rows=ctd.goal_rows.map(num)))
        fa = pd.read_csv(DOCS / f"version_comparison_{tagv}_firm_annual.csv").set_index("fiscalyear")
        yy = [y for y in (1998, 2008, 2015, 2017, 2018, 2020, 2021) if y in fa.index]
        X.table("version_firm_compare", pd.DataFrame({
            "FY": yy, f"Adopt lb {PREV}": [pct(fa.loc[y, f"adopt_lb_{PREV}"]) for y in yy], f"Adopt lb {VER}": [pct(fa.loc[y, f"adopt_lb_{VER}"]) for y in yy],
            f"S lb {PREV}": [pct(fa.loc[y, f"s_lb_{PREV}"]) for y in yy], f"S lb {VER}": [pct(fa.loc[y, f"s_lb_{VER}"]) for y in yy],
            f"G lb {PREV}": [pct(fa.loc[y, f"g_lb_{PREV}"]) for y in yy], f"G lb {VER}": [pct(fa.loc[y, f"g_lb_{VER}"]) for y in yy],
            f"Value share {PREV}": [pct(fa.loc[y, f"value_share_{PREV}"]) for y in yy], f"Value share {VER}": [pct(fa.loc[y, f"value_share_{VER}"]) for y in yy]}))
        for y in (2017, 2018, 2021):
            V[f"prev_lb_{y}"] = pct(fa.loc[y, f"adopt_lb_{PREV}"])
    rf = DOCS / f"review_findings_{VER}.csv"
    if rf.exists():
        R_ = pd.read_csv(rf)
        V.update(n_findings=num(len(R_)), n_findings_high=num((R_.severity == "high").sum()))
        X.table("review_findings", R_[["finding_id", "area", "severity", "finding", "status"]].rename(columns={"finding_id": "ID"}))
    q = VALID / f"human_review_queue_{VER}_local.csv"
    V["n_review_queue"] = num(sum(1 for _ in open(q, encoding="utf-8")) - 1) if q.exists() else "n/a (local file absent)"
    return X


def narrative_block(X):
    bad = [c["claim"] for c in X.checks if not c["ok"]]
    if not bad:
        return f"> Narrative checks: all {len(X.checks)} interpretive statements in this report are supported by the current outputs."
    return ("> **WARNING — narrative checks failed.** The following statements in this report are NOT supported by the current outputs "
            "and the template text must be revised before use:\n" + "\n".join(f"> - {b}" for b in bad))


def fill(template, X):
    V = dict(X.V, narrative_checks=narrative_block(X))
    def rep(m):
        key = m.group(2)
        src = X.T if m.group(1) else V
        if key not in src:
            raise KeyError(f"template placeholder without value: {m.group(0)}")
        return str(src[key])
    return re.sub(r"\{\{(table:)?([A-Za-z0-9_]+)\}\}", rep, template)
