"""Step 09 — Dataset D: ESG_Executive_Firm_Year.dta (unit: CIK x fiscalyear x participantid).

Linkage: grants carry CIK, FiscalYear, FiscalMonth and participantID directly (no cross-year matching needed).
Executive identity comes from ParticipantFY matched EXACTLY on (CIK, FiscalYear, FiscalMonth, participantID);
no name-based or cross-year matching is attempted. If an executive's grants span two fiscal months in the
same fiscal year (fiscal-year-end change), the unit is still (CIK, FY, participantid) and the case is flagged.
"""
import numpy as np, pandas as pd
from config import INTER, read_raw, get_logger, check_unique
from dtautil import write_dta
from aggregate import aggregate, check_aggregate

log = get_logger("09_dataset_D_executive")
C = pd.read_parquet(INTER / "dataset_C.parquet")
K = pd.read_parquet(INTER / "dataset_B.parquet")
A = pd.read_parquet(INTER / "dataset_A.parquet", columns=["text_id", "esg_topics"])
A["esg_topics_strict"] = A.esg_topics.fillna("").apply(lambda s: "|".join(t for t in s.split("|") if t and not t.startswith("X_")))
K = K.merge(A[["text_id", "esg_topics_strict"]], on="text_id", how="left")
K.to_parquet(INTER / "dataset_B_with_topics.parquet", index=False)

P = read_raw("participant")
P = P.rename(columns={"FiscalYear": "fiscalyear", "FiscalMonth": "fiscalmonth", "CIK": "cik"})
rc = P[["roleCode1", "roleCode2", "roleCode3", "roleCode4"]].fillna("").apply(lambda s: s.str.strip())
P["role_codes"] = rc.apply(lambda r: "|".join([x for x in r if x]), axis=1)
P["rolecode_ceo"] = rc.eq("CEO").any(axis=1).astype("int8"); P["rolecode_former"] = rc.isin(["FO", "R"]).any(axis=1).astype("int8")
check_unique(P, ["cik", "fiscalyear", "fiscalmonth", "participantid"], "ParticipantFY", log)
P.to_parquet(INTER / "participant_fy.parquet", index=False)

m = C.merge(P[["cik", "fiscalyear", "fiscalmonth", "participantid"]].assign(_pm=1), on=["cik", "fiscalyear", "fiscalmonth", "participantid"], how="left")
C["participant_matched"] = m._pm.fillna(0).astype("int8").values
log.info(f"grants matched to ParticipantFY on (CIK,FY,FM,pid): {C.participant_matched.mean():.4%}; unmatched {int((C.participant_matched==0).sum())}")
C[C.participant_matched == 0][["grantid", "cik", "fiscalyear", "fiscalmonth", "participantid"]].to_csv(INTER / "audit_grants_unmatched_participant.csv", index=False)
C.to_parquet(INTER / "dataset_C.parquet", index=False)

by = ["cik", "fiscalyear", "participantid"]
D = aggregate(C, K, by, "exec")
fm = C.groupby(by).agg(fiscalmonth=("fiscalmonth", "max"), n_fiscalmonths=("fiscalmonth", "nunique"), _pm=("participant_matched", "mean")).reset_index()
D = D.merge(fm, on=by, how="left")
D["exec_identity_match_status"] = np.where(D._pm == 1, "matched_exact", np.where(D._pm == 0, "unmatched", "partially_matched"))
D["exec_multi_fiscalmonth_flag"] = (D.n_fiscalmonths > 1).astype("int8")
D = D.drop(columns=["_pm", "n_fiscalmonths"])
pi = P.sort_values("fiscalmonth").drop_duplicates(["cik", "fiscalyear", "participantid"], keep="last")
D = D.merge(pi[["cik", "fiscalyear", "participantid", "fullName", "title", "role_codes", "currentCEO", "currentCFO", "CurrentDirector",
                "rolecode_ceo", "rolecode_former", "participantCIK"]], on=["cik", "fiscalyear", "participantid"], how="left")
D = D.rename(columns={"fullName": "exec_name", "title": "exec_title", "role_codes": "exec_role_codes", "currentCEO": "exec_current_ceo_flag",
                      "currentCFO": "exec_current_cfo_flag", "CurrentDirector": "exec_current_director_flag", "rolecode_ceo": "exec_rolecode_ceo",
                      "rolecode_former": "exec_rolecode_former", "participantCIK": "exec_participant_cik"})
check_unique(D, by, "Executive-Firm-Year", log)
check_aggregate(D, "exec", log, "executive")
assert D.exec_n_grants.sum() == len(C), "exec grant counts do not reconcile"
log.info(f"reconciliation: sum(exec_n_grants) = {D.exec_n_grants.sum():,} = grants {len(C):,}")
log.info("identity status:\n" + D.exec_identity_match_status.value_counts().to_string())
D.to_parquet(INTER / "dataset_D.parquet", index=False)
L = dict(cik="Company CIK", fiscalyear="Fiscal year", participantid="ISS participantID", fiscalmonth="Fiscal month (max if >1)",
         exec_name="Full name (ParticipantFY)", exec_title="Title (ParticipantFY)", exec_role_codes="ISS role codes", exec_current_ceo_flag="ISS currentCEO",
         exec_identity_match_status="Exact (CIK,FY,FM,pid) match to ParticipantFY", exec_multi_fiscalmonth_flag="Grants in >1 fiscal month same FY")
write_dta(D, "ESG_Executive_Firm_Year.dta", L, log, keys=by)
