"""Step 15 — Variable dictionary and dataset summary for every final .dta.

中文说明：为每个最终 .dta 的每个变量生成字典：标签、经济含义、计算公式、分子、分母、取值、缺失含义、来源字段。
v1.1 起对所有非模式化变量（数据集 A/B/C、标识、质量字段等）给出逐一的人工定义，不再留空。

Documentation/variable_dictionary.csv columns: dataset, variable (Stata name), preferred_name, label, economic_definition,
calculation, numerator, denominator, possible_values, missing_interpretation, source_fields.
Documentation/dataset_summary.csv: obs, vars, year range, primary key, uniqueness verified.
"""
import re
import numpy as np, pandas as pd
from config import FINAL, INTER, DOCS, get_logger

log = get_logger("15_variable_dictionary")
KEYS = {"ESG_Text_Dictionary.dta": ["text_id"], "ESG_KPI_Master.dta": ["kpi_id"], "ESG_Grant_Master.dta": ["grantid"],
        "ESG_Executive_Firm_Year.dta": ["cik", "fiscalyear", "participantid"], "ESG_CEO_Firm_Year.dta": ["cik", "fiscalyear", "participantid"],
        "ESG_Firm_Year_Master.dta": ["cik", "fiscalyear"], "ESG_NonCEO_Firm_Year.dta": ["cik", "fiscalyear"],
        "ESG_Goal_Record_Classification.dta": ["goal_record_id"]}
UNIT = {"exec": "executive-firm-year", "ceo": "CEO-firm-year", "firm": "firm-year", "nonceo": "non-CEO executives of the firm-year", "grant": "grant", "kpi": "KPI"}
TRI = "1 / 0 / . (Stata missing)"
TRI_MISS = "Unknown: no reliable ESG positive and at least one unresolved condition; or not applicable (no grants in universe)"


def describe(v):
    m = re.match(r"^(exec|ceo|firm|nonceo|grant|kpi)_(.*)$", v)
    p, r = (m.group(1), m.group(2)) if m else ("", v)
    u = UNIT.get(p, "")
    tier = "Extended (Strict + stakeholder)" if ("extended" in r or "_ext" in r) else "Strict"
    univ = ("performance-vesting cash-incentive grants" if "perf_cash" in r else "performance-vesting equity/option grants" if "perf_equity" in r
            else "performance-vesting grants (Abs/Rel/AbsRel)" if "perf" in r else "all grants")
    d = dict(economic_definition="", calculation="", numerator="", denominator="", possible_values="", missing_interpretation="", source_fields="")
    if re.match(r"((perf_)?esg_adopt_(strict|extended|ext|str)|perf_(cash|equity|eq)_esg_adopt_(strict|str))$", r):
        d.update(economic_definition=f"{u} has >=1 {univ[:-1]} with a {tier} ESG performance condition",
                 calculation="1 if any grant ESG=1; 0 if all grants ESG=0; else .", possible_values=TRI, missing_interpretation=TRI_MISS,
                 source_fields="grant_esg_strict / grant_esg_extended <- KPI labels <- metric, metricOther")
    elif re.match(r"esg_[esg]_adopt$", r):
        q = r.split("_")[1].upper()
        d.update(economic_definition=f"{u} has >=1 performance grant with a confirmed {q} condition",
                 calculation=f"1 if any perf grant grant_esg_{q.lower()}=1; 0 if all perf grants Strict ESG=0; else .", possible_values=TRI,
                 missing_interpretation=TRI_MISS + "; general ESG terms (pillar unresolved) also leave it .")
    elif re.match(r"esg_(all|perf|perf_cash|perf_equity)_(grant_share|gshr)_(strict|extended|ext|str)$", r):
        d.update(economic_definition=f"Share of {univ} containing a {tier} ESG condition (exact; only if no grant unresolved)",
                 calculation="numerator / denominator if #unknown grants = 0, else .", numerator=f"# {univ} with ESG=1",
                 denominator=f"# {univ}", possible_values="[0,1] or .", missing_interpretation="unresolved grants present, or no grants in universe; use _lb/_ub")
    elif re.match(r"esg_(all|perf|perf_cash|perf_equity)(_ext)?_share_(lb|ub)$", r):
        b = r[-2:]
        d.update(economic_definition=f"{'Lower' if b=='lb' else 'Upper'} bound of the {tier} ESG share of {univ}",
                 calculation="#ESG/N" if b == "lb" else "(#ESG + #unknown)/N", numerator="# ESG grants" + ("" if b == "lb" else " + # unresolved grants"),
                 denominator=f"# {univ}", possible_values="[0,1]", missing_interpretation="no grants in universe")
    elif re.match(r"esg_kpi_share_(strict|extended)$", r):
        d.update(economic_definition=f"Share of distinct KPIs that are {tier} ESG", calculation="exact only when no KPI unresolved",
                 numerator="# distinct ESG KPIs (goal_source x text_id within unit)", denominator="# distinct KPIs", possible_values="[0,1] or .",
                 missing_interpretation="unresolved KPIs present or no KPIs; use _lb/_ub")
    elif re.match(r"esg_kpi(_ext)?_share_(lb|ub)$", r):
        d.update(economic_definition=f"{'Lower' if r.endswith('lb') else 'Upper'} bound of {tier} ESG KPI share", numerator="# ESG KPIs" + ("" if r.endswith("lb") else " + # unresolved"),
                 denominator="# distinct KPIs", possible_values="[0,1]", missing_interpretation="no KPIs")
    elif re.match(r"[esg]_grant_share(_lb|_ub)?$", r):
        q, b = r[0].upper(), r[-2:]
        kind = "lower bound" if b == "lb" else "upper bound" if b == "ub" else "exact (only if every performance grant's pillar label is known)"
        d.update(economic_definition=f"Share of performance grants with a {q} condition — {kind}",
                 numerator=f"# perf grants with grant_esg_{r[0]}=1" + (" + # perf grants with unknown pillar" if b == "ub" else ""),
                 denominator="# performance grants", possible_values="[0,1]" + (" or ." if kind.startswith("exact") else ""),
                 missing_interpretation="no performance grants" + ("; or some pillar labels unknown (use _lb/_ub)" if kind.startswith("exact") else ""))
    elif re.match(r"[esg]_kpi_share(_lb|_ub)?$", r):
        q, b = r[0].upper(), r[-2:]
        kind = "lower bound" if b == "lb" else "upper bound" if b == "ub" else "exact (only if every KPI's pillar label is known)"
        d.update(economic_definition=f"Share of distinct KPIs with a {q} condition — {kind}", numerator=f"# KPIs with esg_{r[0]}=1" + (" + # KPIs with unknown pillar" if b == "ub" else ""),
                 denominator="# distinct KPIs", possible_values="[0,1]" + (" or ." if kind.startswith("exact") else ""),
                 missing_interpretation="no KPIs" + ("; or some pillar labels unknown (use _lb/_ub)" if kind.startswith("exact") else ""))
    elif "coverage" in r:
        d.update(economic_definition="Share of units in the denominator whose Strict ESG status is known", numerator="# classified (1 or 0)",
                 denominator="# grants / KPIs in universe", possible_values="[0,1]", missing_interpretation="empty universe")
    elif r.startswith("n_"):
        d.update(economic_definition=f"Count ({r[2:].replace('_', ' ')}) for the {u or 'unit'}", possible_values="integer >= 0", missing_interpretation="none")
    elif "compensation_value_share" in r:
        d.update(economic_definition="Value of grants containing >=1 Strict ESG condition / value of all grants with a reported value; value = grant-date "
                 "fair value, or the non-equity target payout for cash awards (v1.1). EXPOSURE, NOT value attributable to ESG (KPI weights not reliably observable)",
                 numerator="sum grant_value_combined of ESG grants", denominator="sum grant_value_combined of grants (in universe)", possible_values="[0,1]",
                 missing_interpretation="no grant with a reported value", source_fields="grantDateFV, nonEquityTarget (-9999 codes -> .)")
    elif r == "esg_measurement_complete":
        d.update(economic_definition="1 if every performance grant is classified (no unresolved grant)", possible_values="1/0/.", missing_interpretation="no performance grants")
    elif "diag" in r:
        d.update(economic_definition="DIAGNOSTIC ONLY: based on ISS metricType (Social/Environment/CSR) or 2018 ESG metric labels; never used for primary labels",
                 source_fields="metricType, metric")
    elif r in ("esg_metric_count",):
        d.update(economic_definition="Number of distinct Strict ESG metric texts used", possible_values="integer >= 0")
    elif r == "esg_metric_diversity":
        d.update(economic_definition="Number of distinct Strict ESG topics (e.g. S_ohs, E_ghg_air) among KPIs", possible_values="integer >= 0")
    elif r == "esg_e_s_g_diversity":
        d.update(economic_definition="Number of pillars (E, S, G) with >=1 confirmed KPI", possible_values="0-3")
    return d


GEN = {  # explicit definitions for non-pattern variables (economic definition, source fields, missing meaning)
 "text_id": ("Stable identifier of a classification unit = 'T' + first 10 hex digits of SHA-1(text_key)", "text_key", "never missing"),
 "text_key": ("Standardized classification key: metric || lower(normalized metricOther) [|| ctx=<structured context>]", "metric, metricOther", "never missing"),
 "text_original": ("Most frequent raw spelling of metricOther within the unit", "metricOther", "blank = ISS left the text empty"),
 "text_normalized": ("metricOther after NFKC normalisation, quote/dash normalisation, whitespace collapse, trailing punctuation removal, lower case", "metricOther", "blank = no text"),
 "metric": ("ISS standardized metric label (read jointly with metricOther; 2018-taxonomy ESG labels never used as evidence)", "metric", "blank = ISS left it empty"),
 "classification_context": ("Structured context admitted only when metricOther is blank and metric is a placeholder: fin_metrictype / no_text / iss_esg_label_only", "metricType", "blank = text was informative"),
 "esg_strict": ("Strict ESG: the performance condition explicitly references an environmental, social or governance objective", "rules on metric+metricOther (or human label)", "Unknown: insufficient information"),
 "esg_extended": ("Extended ESG: Strict ESG or an explicit stakeholder (customer, product responsibility, community, service reliability) objective", "rules / human label", "Unknown"),
 "esg_extended_only": ("1 if Extended but not Strict; 0 if not Extended or Strict; . if undecidable", "esg_strict, esg_extended", "Unknown"),
 "esg_e": ("Strict ESG with an explicit environmental component", "rules", "Unknown: Strict unknown, or general ESG term / ambiguous E word leaves pillar unresolved"),
 "esg_s": ("Strict ESG with an explicit social component", "rules", "Unknown (see esg_e)"),
 "esg_g": ("Strict ESG with an explicit, specific governance component", "rules", "Unknown (see esg_e)"),
 "esg_general": ("1 if a multi-pillar term (ESG, CSR, sustainability, citizenship, ESG ratings) fired", "rules", "none"),
 "esg_strict_textonly": ("Strict label using text only (no structured metricType context)", "rules", "Unknown"),
 "esg_extended_textonly": ("Extended label using text only", "rules", "Unknown"),
 "classification_status": ("confirmed = adjudicated human label; provisional = rule label not yet human-verified; unknown = unresolved", "", "none"),
 "classification_method": ("deterministic_rule / structured_context / human_review / unresolved", "", "none"),
 "classification_confidence": ("high / medium / low (rule confidence) or human", "", "none"),
 "classification_reason": ("Every rule that fired with the matched text, masks applied, and label notes (full audit trail)", "", "none"),
 "esg_topics": ("ESG and stakeholder topics matched (see Dictionaries/b_revised_rules)", "rules", "blank = none"),
 "adjacent_flags": ("ESG-adjacent exclusions that fired (J_*: compliance/risk, generic workforce, public affairs, renewable or ESG business line)", "rules", "blank = none"),
 "review_flags": ("Rule-conflict flags (ESG term under financial label, mixed ESG+financial text, ESG inside composite description)", "rules", "blank = none"),
 "review_priority": ("Priority for the human review queue", "", "blank = not queued"),
 "rule_ids": ("Identifiers of all rules that fired", "Dictionaries/b_revised_rules_<v>.csv", "none"),
 "human_reviewed": ("1 if an adjudicated human label overrides the rule label", "Validation/human_labels/adjudicated_labels.csv", "none"),
 "paper_esg": ("AGHJ (2025) 953-keyword match on metricOther; . if metricOther blank (paper cannot classify)", "metricOther", "blank text"),
 "paper_esg_as_used": ("AGHJ (2025) rule as applied in the paper: match = 1, no match or blank = 0", "metricOther", "none"),
 "paper_terms": ("AGHJ keywords matched", "metricOther", "blank = none"),
 "iss_esg_share_diag": ("DIAGNOSTIC ONLY: share of the unit's goal records with ISS ESG metricType (Social/Environment/CSR) or 2018 ESG metric label", "metricType, metric", "none"),
 "metrictype_mode": ("Most frequent ISS metricType of the unit (diagnostic)", "metricType", "none"),
 "first_year": ("Earliest fiscal year in which the unit occurs", "fiscalYear", "none"),
 "last_year": ("Latest fiscal year in which the unit occurs", "fiscalYear", "none"),
 "n_goal_rows": ("Number of raw goal records (objective x period) with this unit", "goal files", "none"),
 "n_rows_pre2018": ("Goal records before fiscal 2018", "goal files", "none"),
 "n_grants": ("Distinct grants containing the unit", "grantId", "none"),
 "n_firms": ("Distinct firms (CIK) using the unit", "CIK", "none"),
 "classifier_version": ("Classifier version that produced the labels", "", "none"),
 "kpi_id": ("KPI identifier = goal_source + grantid + text_id", "", "none"),
 "grantid": ("ISS grant identifier", "grantID", "none"),
 "goal_id": ("Representative (minimum) ISS objective id (absId/relId/accId); ids are recycled across grants", "absId/relId/accId", "none"),
 "goal_source": ("ABS = absolute, REL = relative, ACC = accelerated performance goal file", "", "none"),
 "participantid": ("ISS participant (executive) identifier", "participantID", "none"),
 "cik": ("SEC Central Index Key of the company", "CIK", "none"),
 "fiscalyear": ("ISS fiscal year (FYE on/before 10 July -> previous calendar year)", "fiscalYear", "none"),
 "fiscalmonth": ("ISS fiscal month", "fiscalMonth", "not reported"),
 "metricother": ("Raw ISS metricOther text", "metricOther", "blank = not reported"),
 "metrictype_original": ("Raw ISS metricType (diagnostic only; categories changed in 2018)", "metricType", "blank"),
 "kpi_duplicate_flag": ("1 if the same text appears in >1 ISS objective of the grant (collapsed into one KPI)", "", "none"),
 "kpi_source_count": ("Number of raw goal records collapsed into the KPI", "", "none"),
 "kpi_key_complete": ("1 if grant, CIK, year and participant are all present and the grant exists", "", "none"),
 "grant_type": ("cash_incentive (cashShort/cashLong/unitCash) / stock_like / option_like / other_or_missing", "awardType", "none"),
 "performancetype": ("ISS performance type Abs/Rel/AbsRel/Time (duplicates resolved from goal data in v1.1)", "performanceType", "blank = missing"),
 "grant_value": ("Grant-date fair value as reported (USD); -9999 codes and negative values set to missing", "grantDateFV", "not reported (typical for cash awards)"),
 "grant_value_combined": ("Grant value used for exposure shares: fair value, or non-equity target payout for cash awards", "grantDateFV, nonEquityTarget", "neither reported"),
 "grant_goal_status": ("perf_with_goals / perf_goals_missing / time_no_perf_condition / time_with_accel_goals / time_accel_declared_goals_missing / type_missing", "", "none"),
 "ceo_identification_status": ("unique_current_ceo_flag / multiple_current_ceo_flags / rolecode_fallback_unique", "currentCEO, roleCode1-4", "none"),
 "ceo_strict_sample": ("1 = the firm-year has exactly one participant with currentCEO = 1", "currentCEO", "none"),
 "exec_identity_match_status": ("matched_exact / partially_matched / unmatched to ParticipantFY on (CIK, FY, FM, pid)", "", "none"),
 "company_name": ("Company name (CompanyFY)", "companyName", "none"), "ticker": ("Ticker (CompanyFY)", "ticker", "blank"), "cusip": ("8-digit CUSIP (CompanyFY)", "CUSIP", "blank"),
}
GEN_SUFFIX = {  # prefix-independent fields
 "esg_text_ids": ("text_ids of the unit's Strict ESG KPIs (trace to Dataset A / KPI master)", "", "blank = none"),
 "total_grant_value": ("Sum of grant_value_combined over grants with a reported value", "grantDateFV, nonEquityTarget", "no grant with value"),
 "value_coverage": ("Share of grants with a reported grant_value_combined", "", "no grants"),
}

rows, summ = [], []
for f, keys in KEYS.items():
    path = FINAL / f
    if not path.exists():
        continue
    rd = pd.io.stata.StataReader(path)
    with rd:
        labels = rd.variable_labels()
    df = pd.read_stata(path, convert_categoricals=False)
    vm = pd.read_csv(INTER / f"varmap_{f}.csv").set_index("stata_name").preferred_name.to_dict() if (INTER / f"varmap_{f}.csv").exists() else {}
    yrcol = "fiscalyear" if "fiscalyear" in df.columns else ("first_year" if "first_year" in df.columns else None)
    summ.append(dict(dataset=f, observations=len(df), variables=df.shape[1], primary_key="+".join(keys),
                     key_unique=bool(not df.duplicated(keys).any()), key_missing=int(df[keys].isna().any(axis=1).sum()),
                     year_min=df[yrcol].min() if yrcol else None, year_max=(df["last_year"].max() if yrcol == "first_year" else df[yrcol].max()) if yrcol else None))
    for c in df.columns:
        pref = vm.get(c, c)
        d = describe(pref)
        base = pref.split("_", 1)[1] if pref.split("_", 1)[0] in ("exec", "ceo", "firm", "nonceo") and "_" in pref else pref
        key = pref if pref in GEN else (base if base in GEN_SUFFIX else None)
        if key is not None and not d["economic_definition"]:
            econ, src, miss = GEN.get(key) or GEN_SUFFIX.get(key)
            d.update(economic_definition=econ, source_fields=src or d["source_fields"], missing_interpretation=miss)
        if not d["economic_definition"]:
            d["economic_definition"] = labels.get(c, "")
        s = df[c]
        if not d["possible_values"]:
            if pd.api.types.is_numeric_dtype(s):
                vals = sorted(s.dropna().unique())
                d["possible_values"] = ("/".join(str(int(v)) if float(v).is_integer() else str(v) for v in vals) if len(vals) <= 4 else f"numeric [{s.min():.4g}, {s.max():.4g}]")
            else:
                d["possible_values"] = f"text ({s.nunique()} distinct)"
        if not d["missing_interpretation"]:
            d["missing_interpretation"] = "not reported / not applicable" if s.isna().any() else "none"
        rows.append(dict(dataset=f, variable=c, preferred_name=pref, label=labels.get(c, ""), n_nonmissing=int(s.notna().sum()), **d))
vd = pd.DataFrame(rows)
vd.to_csv(DOCS / "variable_dictionary.csv", index=False)
pd.DataFrame(summ).to_csv(DOCS / "dataset_summary.csv", index=False)
log.info("dataset summary:\n" + pd.DataFrame(summ).to_string(index=False))
log.info(f"variable dictionary: {len(vd)} variables")
