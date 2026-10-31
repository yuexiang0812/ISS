"""Step 15 — Variable dictionary and dataset summary for every final .dta.

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
    univ = "performance-vesting grants (Abs/Rel/AbsRel)" if "perf" in r else "all grants"
    d = dict(economic_definition="", calculation="", numerator="", denominator="", possible_values="", missing_interpretation="", source_fields="")
    if re.match(r"(perf_)?esg_adopt_(strict|extended)$", r):
        d.update(economic_definition=f"{u} has >=1 {univ[:-1]} with a {tier} ESG performance condition",
                 calculation="1 if any grant ESG=1; 0 if all grants ESG=0; else .", possible_values=TRI, missing_interpretation=TRI_MISS,
                 source_fields="grant_esg_strict / grant_esg_extended <- KPI labels <- metric, metricOther")
    elif re.match(r"esg_[esg]_adopt$", r):
        q = r.split("_")[1].upper()
        d.update(economic_definition=f"{u} has >=1 performance grant with a confirmed {q} condition",
                 calculation=f"1 if any perf grant grant_esg_{q.lower()}=1; 0 if all perf grants Strict ESG=0; else .", possible_values=TRI,
                 missing_interpretation=TRI_MISS + "; general ESG terms (pillar unresolved) also leave it .")
    elif re.match(r"esg_(all|perf)_grant_share_(strict|extended|ext|str)$", r):
        d.update(economic_definition=f"Share of {univ} containing a {tier} ESG condition (exact; only if no grant unresolved)",
                 calculation="numerator / denominator if #unknown grants = 0, else .", numerator=f"# {univ} with ESG=1",
                 denominator=f"# {univ}", possible_values="[0,1] or .", missing_interpretation="unresolved grants present, or no grants in universe; use _lb/_ub")
    elif re.match(r"esg_(all|perf)(_ext)?_share_(lb|ub)$", r):
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
    elif re.match(r"[esg]_grant_share$", r):
        q = r[0].upper()
        d.update(economic_definition=f"Share of performance grants with a confirmed {q} condition (lower bound)", numerator=f"# perf grants with grant_esg_{r[0]}=1",
                 denominator="# performance grants", possible_values="[0,1]", missing_interpretation="no performance grants")
    elif re.match(r"[esg]_kpi_share$", r):
        q = r[0].upper()
        d.update(economic_definition=f"Share of distinct KPIs with a confirmed {q} condition", numerator=f"# KPIs with esg_{r[0]}=1", denominator="# distinct KPIs",
                 possible_values="[0,1] or .", missing_interpretation="unresolved KPIs present or no KPIs")
    elif "coverage" in r:
        d.update(economic_definition="Share of units in the denominator whose Strict ESG status is known", numerator="# classified (1 or 0)",
                 denominator="# grants / KPIs in universe", possible_values="[0,1]", missing_interpretation="empty universe")
    elif r.startswith("n_"):
        d.update(economic_definition=f"Count ({r[2:].replace('_', ' ')}) for the {u or 'unit'}", possible_values="integer >= 0", missing_interpretation="none")
    elif "compensation_value_share" in r:
        d.update(economic_definition="Grant-date fair value of grants containing >=1 Strict ESG condition / fair value of all grants with reported value. "
                 "NOT value attributable to ESG (KPI weights not reliably observable)", numerator="sum grant_value of ESG grants",
                 denominator="sum grant_value of grants (in universe)", possible_values="[0,1]", missing_interpretation="no grant with reported fair value",
                 source_fields="grantDateFV (-9999 codes -> .)")
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
