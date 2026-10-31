"""Step 16 — Independent quality audit of the FINAL .dta outputs (re-read from disk).

Every check is recorded as PASS / FAIL / WARN / INFO in Documentation/quality_audit_results.csv.
Key logic is RE-DERIVED here from lower-level datasets (not copied from the build steps), so the audit can catch
build errors: grant ESG from KPIs, firm counts from grants, executive/firm adoption identities, label consistency.
The step fails (non-zero exit) if any FAIL is recorded.
"""
import json, sys, hashlib, datetime as dt
import numpy as np, pandas as pd
from config import FINAL, INTER, DOCS, VALID, CLASSIFIER_VERSION, get_logger

log = get_logger("16_quality_audit")
R = []
def rec(dataset, check, ok, value="", detail="", level=None):
    status = level or ("PASS" if ok else "FAIL")
    R.append(dict(check_id=f"Q{len(R)+1:03d}", dataset=dataset, check=check, status=status, value=str(value), detail=detail))
    log.info(f"[{status}] {dataset}: {check} = {value} {detail}")

rd = lambda f, cols=None: pd.read_stata(FINAL / f, columns=cols, convert_categoricals=False)
TRI = lambda s: s.dropna().isin([0, 1]).all()

# ---------------- A text dictionary
A = rd("ESG_Text_Dictionary.dta")
rec("A", "primary key text_id unique & non-missing", A.text_id.is_unique and A.text_id.ne("").all(), len(A))
rec("A", "text_key unique (one label per text unit)", A.text_key.is_unique, A.text_key.nunique())
for c in ["esg_strict", "esg_extended", "esg_extended_only", "esg_e", "esg_s", "esg_g"]:
    rec("A", f"{c} in {{0,1,.}}", TRI(A[c]), A[c].value_counts(dropna=False).to_dict())
rec("A", "Strict=1 implies Extended=1", not ((A.esg_strict == 1) & (A.esg_extended != 1)).any())
rec("A", "E/S/G=1 implies Strict=1", not (((A.esg_e == 1) | (A.esg_s == 1) | (A.esg_g == 1)) & (A.esg_strict != 1)).any())
rec("A", "extended_only = Extended & not Strict", ((A.esg_extended_only == 1) == ((A.esg_extended == 1) & (A.esg_strict != 1))).all())
rec("A", "status consistent (unknown <=> strict missing; confirmed <=> human_reviewed)",
    ((A.classification_status == "unknown") == A.esg_strict.isna()).all() and ((A.classification_status == "confirmed") == (A.human_reviewed == 1)).all())
rec("A", "every label has a method and a reason", A.classification_method.ne("").all() and A.classification_reason.ne("").all())
rec("A", "classifier_version recorded", (A.classifier_version == CLASSIFIER_VERSION).all(), CLASSIFIER_VERSION)
rec("A", "year range within 1998-2021", A.first_year.min() >= 1998 and A.last_year.max() <= 2021, f"{A.first_year.min()}-{A.last_year.max()}")
rec("A", "share of units Unknown (Strict)", True, round(A.esg_strict.isna().mean(), 4), level="INFO")
rec("A", "units using structured context (blank text)", True, int((A.classification_method == "structured_context").sum()), level="INFO")
rec("A", "human-reviewed units", True, int(A.human_reviewed.sum()), level="WARN" if A.human_reviewed.sum() == 0 else "INFO")

# ---------------- goal records & B KPI master
G = rd("ESG_Goal_Record_Classification.dta", ["goal_record_id", "grantid", "text_id", "fiscalyear", "esg_strict", "esg_extended", "goal_grant_matched"])
rec("B-alt", "goal_record_id unique", G.goal_record_id.is_unique, len(G))
lab = A.set_index("text_id")
rec("B-alt", "goal-record labels equal dictionary labels (same text -> same label in every year)",
    np.allclose(G.esg_strict.fillna(-1), G.text_id.map(lab.esg_strict).fillna(-1)), "")
cons = G.groupby("text_id").esg_strict.nunique(dropna=False)
rec("B-alt", "no text unit has >1 Strict label across years", (cons <= 1).all(), int((cons > 1).sum()))
rec("B-alt", "goal records not matched to a grant", True, int((G.goal_grant_matched == 0).sum()), level="INFO")
K = rd("ESG_KPI_Master.dta", ["kpi_id", "grantid", "goal_source", "text_id", "cik", "fiscalyear", "participantid", "kpi_source_count",
                               "kpi_esg_strict", "kpi_esg_extended", "kpi_esg_e", "kpi_esg_s", "kpi_esg_g", "kpi_key_complete", "kpi_duplicate_flag"])
rec("B", "primary key kpi_id unique", K.kpi_id.is_unique, len(K))
rec("B", "(grantid, goal_source, text_id) unique", not K.duplicated(["grantid", "goal_source", "text_id"]).any())
rec("B", "sum kpi_source_count = goal records", K.kpi_source_count.sum() == len(G), f"{K.kpi_source_count.sum():,} vs {len(G):,}")
rec("B", "KPI labels equal dictionary labels", np.allclose(K.kpi_esg_strict.fillna(-1), K.text_id.map(lab.esg_strict).fillna(-1)) and
    np.allclose(K.kpi_esg_extended.fillna(-1), K.text_id.map(lab.esg_extended).fillna(-1)))
rec("B", "missing identifiers (cik/fiscalyear/participantid)", True, int(K[["cik", "fiscalyear", "participantid"]].isna().any(axis=1).sum() + (K.cik == "").sum()),
    level="INFO")
rec("B", "KPIs with incomplete keys", True, int((K.kpi_key_complete == 0).sum()), level="INFO")
rec("B", "fiscalyear within 1998-2021", K.fiscalyear.dropna().between(1998, 2021).all())

# ---------------- C grant master
C = rd("ESG_Grant_Master.dta")
rec("C", "primary key grantid unique & non-missing", C.grantid.is_unique and C.grantid.notna().all(), len(C))
rec("C", "no missing cik / fiscalyear / participantid", C[["fiscalyear", "participantid"]].notna().all().all() and C.cik.ne("").all())
for c in ["grant_esg_strict", "grant_esg_extended", "grant_esg_e", "grant_esg_s", "grant_esg_g"]:
    rec("C", f"{c} in {{0,1,.}}", TRI(C[c]))
rec("C", "no negative grant_value", not (C.grant_value < 0).any(), int((C.grant_value < 0).sum()))
rec("C", "grant_date not before 1990 or after 2023", C.grant_date.dropna().between(pd.Timestamp("1990-01-01"), pd.Timestamp("2023-12-31")).all(),
    f"{C.grant_date.min()} - {C.grant_date.max()}")
rec("C", "expiration_date >= grant_date (where both present)", True,
    int(((C.expiration_date < C.grant_date) & C.expiration_date.notna() & C.grant_date.notna()).sum()), level="INFO")
rec("C", "grant dates flagged suspect", True, int(C.grant_date_suspect.sum()), level="INFO")
# re-derive grant ESG from KPI master
kk = K.groupby("grantid").agg(n=("kpi_id", "size"), p=("kpi_esg_strict", lambda s: (s == 1).sum()), u=("kpi_esg_strict", lambda s: s.isna().sum()))
m = C.set_index("grantid").join(kk, how="left").fillna({"n": 0, "p": 0, "u": 0})
red = np.where(m.p > 0, 1.0, np.where((m.n > 0) & (m.u == 0), 0.0, np.nan))
red = np.where(m.grant_goal_status == "time_no_perf_condition", 0.0, red)
rec("C", "grant_esg_strict re-derived from KPI master matches", np.allclose(m.grant_esg_strict.fillna(-1), pd.Series(red).fillna(-1)))
rec("C", "grant_n_kpis matches KPI master", (m.grant_n_kpis == m.n).all())
rec("C", "esg + non-esg + unknown KPIs = n_kpis", (C.grant_n_esg_kpis_strict + C.grant_n_non_esg_kpis + C.grant_n_unknown_kpis == C.grant_n_kpis).all())
rec("C", "time grants without perf condition have no KPIs", (C.loc[C.grant_goal_status == "time_no_perf_condition", "grant_n_kpis"] == 0).all())
rec("C", "perf grants with missing goal data (Unknown, not 0)", C.loc[C.grant_goal_status == "perf_goals_missing", "grant_esg_strict"].isna().all(),
    int((C.grant_goal_status == "perf_goals_missing").sum()))

def shares_ok(df, name):
    cols = [c for c in df.columns if ("share" in c or "coverage" in c) and df[c].dtype.kind == "f"]
    bad = {c: int(((df[c] < -1e-9) | (df[c] > 1 + 1e-9)).sum()) for c in cols}
    rec(name, f"all {len(cols)} share/coverage variables within [0,1]", sum(bad.values()) == 0, sum(bad.values()))
    pairs = [(c, c[:-2] + "ub") for c in df.columns if c.endswith("_lb") and c[:-2] + "ub" in df.columns]
    bad2 = sum(int((df[a] > df[b] + 1e-9).sum()) for a, b in pairs)
    rec(name, f"lower bound <= upper bound ({len(pairs)} pairs)", bad2 == 0, bad2)
shares_ok(C, "C")

# ---------------- D executive
D = rd("ESG_Executive_Firm_Year.dta")
rec("D", "primary key (cik, fiscalyear, participantid) unique", not D.duplicated(["cik", "fiscalyear", "participantid"]).any(), len(D))
rec("D", "sum exec_n_grants = grants", D.exec_n_grants.sum() == len(C), f"{D.exec_n_grants.sum():,}")
cg = C.groupby(["cik", "fiscalyear", "participantid"]).agg(n=("grantid", "size"), s1=("grant_esg_strict", lambda s: (s == 1).sum()))
dj = D.set_index(["cik", "fiscalyear", "participantid"]).join(cg)
rec("D", "exec grant / ESG-grant counts re-derived from grant master", (dj.exec_n_grants == dj.n).all() and (dj.exec_n_esg_grants_strict == dj.s1).all())
rec("D", "adoption=1 iff >=1 ESG grant", ((D.exec_esg_adopt_strict == 1) == (D.exec_n_esg_grants_strict > 0)).all())
shares_ok(D, "D")
rec("D", "identity match status", True, D.exec_identity_match_status.value_counts().to_dict(), level="INFO")

# ---------------- E CEO
E = rd("ESG_CEO_Firm_Year.dta")
rec("E", "primary key unique", not E.duplicated(["cik", "fiscalyear", "participantid"]).any(), len(E))
rec("E", "strict CEO sample: exactly one CEO per firm-year", (E[E.ceo_strict_sample == 1].groupby(["cik", "fiscalyear"]).size() == 1).all(),
    int(E.ceo_strict_sample.sum()))
rec("E", "every CEO row exists as an executive-year or has no grants", (E.ceo_has_grants == 0).sum() + E.merge(D[["cik", "fiscalyear", "participantid"]],
    on=["cik", "fiscalyear", "participantid"]).shape[0] == len(E))
rec("E", "CEO identification status", True, E.ceo_identification_status.value_counts().to_dict(), level="INFO")
shares_ok(E, "E")

# ---------------- F firm & G non-CEO
F = rd("ESG_Firm_Year_Master.dta")
rec("F", "primary key (cik, fiscalyear) unique", not F.duplicated(["cik", "fiscalyear"]).any(), len(F))
rec("F", "sum firm_n_grants = grants", F.firm_n_grants.sum() == len(C))
fx = D.groupby(["cik", "fiscalyear"])[["exec_n_grants", "exec_n_perf_grants", "exec_n_esg_grants_strict", "exec_n_unknown_grants"]].sum()
fj = F.set_index(["cik", "fiscalyear"]).join(fx, how="inner")
rec("F", "firm counts = sum over executive-years (grants, perf, ESG, unknown)",
    (fj.firm_n_grants == fj.exec_n_grants).all() and (fj.firm_n_perf_grants == fj.exec_n_perf_grants).all() and
    (fj.firm_n_esg_grants_strict == fj.exec_n_esg_grants_strict).all() and (fj.firm_n_unknown_grants == fj.exec_n_unknown_grants).all())
ea = D.groupby(["cik", "fiscalyear"]).exec_esg_adopt_strict.apply(lambda s: 1.0 if (s == 1).any() else (0.0 if (s == 0).all() else np.nan))
fa = F.set_index(["cik", "fiscalyear"]).firm_esg_adopt_strict.reindex(ea.index)
rec("F", "firm adoption = aggregation of executive adoption", np.allclose(fa.fillna(-1), ea.fillna(-1)))
rec("F", "firm-years without grants have missing (not 0) ESG measures", F.loc[F.firm_has_grants == 0, "firm_esg_adopt_strict"].isna().all(),
    int((F.firm_has_grants == 0).sum()))
shares_ok(F, "F")
Gn = rd("ESG_NonCEO_Firm_Year.dta")
rec("G", "primary key (cik, fiscalyear) unique", not Gn.duplicated(["cik", "fiscalyear"]).any(), len(Gn))
gg = Gn.set_index(["cik", "fiscalyear"]).join(F.set_index(["cik", "fiscalyear"])[["firm_n_grants"]])
rec("G", "non-CEO grants <= firm grants", (gg.nonceo_n_grants <= gg.firm_n_grants).all())
shares_ok(Gn, "G")

# ---------------- audit tables & validation status
for f in ["audit_goal_grants_missing_in_grant_table.csv", "audit_grants_unmatched_participant.csv", "audit_ceo_exceptions.csv"]:
    p = INTER / f
    rec("audit", f, p.exists(), (sum(1 for _ in open(p)) - 1) if p.exists() else "missing", level="INFO" if p.exists() else "FAIL")
vs = json.loads((VALID / f"validation_status_{CLASSIFIER_VERSION}.json").read_text()) if (VALID / f"validation_status_{CLASSIFIER_VERSION}.json").exists() else {}
rec("validation", "independent human validation", vs.get("status") != "pending_human_labels", vs.get("status", "metrics computed"),
    "labels are PROVISIONAL until human labels exist", level="WARN" if vs.get("status") == "pending_human_labels" else "INFO")

out = pd.DataFrame(R)
out["audit_timestamp"] = dt.datetime.now().isoformat(timespec="seconds")
out.to_csv(DOCS / "quality_audit_results.csv", index=False)
s = out.status.value_counts().to_dict()
log.info(f"audit summary: {s}")
if s.get("FAIL", 0):
    sys.exit(f"{s['FAIL']} audit checks FAILED")
