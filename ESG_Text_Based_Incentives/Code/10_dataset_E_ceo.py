"""Step 10 — Dataset E: ESG_CEO_Firm_Year.dta + CEO exception table.

中文说明：CEO 识别以 ParticipantFY 的 currentCEO 标记为准；唯一标记进入严格样本；多个标记（联席 CEO / 交接）全部保留但不进严格样本，
并列入例外表；无标记时仅当角色代码唯一为 CEO 才作为备选；UC（分部 CEO）不算公司 CEO。没有 grant 的 CEO 计数记 0、指标缺失。

CEO identification (ParticipantFY, per CIK x fiscalyear, all fiscal months of that FY):
  unique_current_ceo_flag     exactly one participant with currentCEO = 1             -> strict CEO sample (ceo_strict_sample = 1)
  multiple_current_ceo_flags  2+ participants with currentCEO = 1 (co-CEOs / succession) -> all candidates kept, ceo_strict_sample = 0,
                                                                                         listed in exception table (none silently selected)
  rolecode_fallback_unique    no currentCEO = 1, exactly one roleCode 'CEO' (not FO/R) and currentCEO not explicitly 0
                                                                                      -> kept, ceo_strict_sample = 0 (alternative sample)
  no_ceo_identified / rolecode_ambiguous                                              -> exception table only
Role code 'UC' (segment CEO) is never treated as company CEO.
"""
import numpy as np, pandas as pd
from config import INTER, get_logger, check_unique
from dtautil import write_dta
from aggregate import fill_counts

log = get_logger("10_dataset_E_ceo")
P = pd.read_parquet(INTER / "participant_fy.parquet")
D = pd.read_parquet(INTER / "dataset_D.parquet")
fyk = ["cik", "fiscalyear"]
pp = P.groupby(fyk + ["participantid"]).agg(cur=("currentCEO", "max"), cur_min=("currentCEO", "min"), rc=("rolecode_ceo", "max"),
                                            fo=("rolecode_former", "max"), name=("fullName", "last"), title=("title", "last")).reset_index()
flag = pp[pp.cur == 1]
nf = flag.groupby(fyk).participantid.nunique().rename("n_flag")
rcc = pp[(pp.rc == 1) & (pp.fo == 0) & ~(pp.cur_min == 0)]
nr = rcc.groupby(fyk).participantid.nunique().rename("n_rc")
fy = pp[fyk].drop_duplicates().set_index(fyk).join(nf).join(nr).fillna(0)
fy["ceo_identification_status"] = np.select(
    [fy.n_flag == 1, fy.n_flag >= 2, (fy.n_flag == 0) & (fy.n_rc == 1), (fy.n_flag == 0) & (fy.n_rc >= 2)],
    ["unique_current_ceo_flag", "multiple_current_ceo_flags", "rolecode_fallback_unique", "rolecode_ambiguous"], "no_ceo_identified")
log.info("firm-year CEO identification status:\n" + fy.ceo_identification_status.value_counts().to_string())
fy = fy.reset_index()
fy.to_parquet(INTER / "ceo_status_firmyear.parquet", index=False)

cand = pd.concat([flag.merge(fy[fy.ceo_identification_status.isin(["unique_current_ceo_flag", "multiple_current_ceo_flags"])], on=fyk),
                  rcc.merge(fy[fy.ceo_identification_status == "rolecode_fallback_unique"], on=fyk)], ignore_index=True)
cand["ceo_strict_sample"] = (cand.ceo_identification_status == "unique_current_ceo_flag").astype("int8")
cand["ceo_flag_with_former_rolecode"] = cand.fo.astype("int8")
# exception table: every candidate in non-unique firm-years + firm-years with no CEO
exc = pd.concat([cand[cand.ceo_strict_sample == 0][fyk + ["participantid", "name", "title", "cur", "rc", "fo", "ceo_identification_status"]],
                 pp.merge(fy[fy.ceo_identification_status.isin(["rolecode_ambiguous", "no_ceo_identified"])], on=fyk)
                   .query("rc == 1 or cur == 1")[fyk + ["participantid", "name", "title", "cur", "rc", "fo", "ceo_identification_status"]]],
                ignore_index=True)
noceo = fy[fy.ceo_identification_status == "no_ceo_identified"][fyk + ["ceo_identification_status"]]
exc = pd.concat([exc, noceo], ignore_index=True).sort_values(fyk)
exc.rename(columns={"cur": "currentceo_flag", "rc": "rolecode_ceo", "fo": "rolecode_former_or_retired"}).to_csv(
    INTER / "audit_ceo_exceptions.csv", index=False)
log.info(f"exception table rows: {len(exc):,} (firm-years: {exc[fyk].drop_duplicates().shape[0]:,})")

E = cand[fyk + ["participantid", "name", "title", "ceo_identification_status", "ceo_strict_sample", "ceo_flag_with_former_rolecode"]].rename(
    columns={"name": "ceo_name", "title": "ceo_title"})
dcols = [c for c in D.columns if c.startswith("exec_") and c not in ("exec_name", "exec_title")]
E = E.merge(D[fyk + ["participantid"] + dcols], on=fyk + ["participantid"], how="left")
E = E.rename(columns={c: "ceo_" + c[5:] for c in dcols})
E["ceo_has_grants"] = E.ceo_n_grants.fillna(0).gt(0).astype("int8")
E = fill_counts(E, "ceo")      # v1.1: all count variables 0 (not missing) for CEOs without grants
check_unique(E, fyk + ["participantid"], "CEO-Firm-Year", log)
assert (E[E.ceo_strict_sample == 1].groupby(fyk).size() == 1).all(), "strict CEO sample must be unique per firm-year"
log.info(f"CEO-firm-years: {len(E):,}; strict sample {int(E.ceo_strict_sample.sum()):,}; with grants {int(E.ceo_has_grants.sum()):,}")
E.to_parquet(INTER / "dataset_E.parquet", index=False)
L = dict(cik="Company CIK", fiscalyear="Fiscal year", participantid="ISS participantID of CEO", ceo_name="CEO full name (ParticipantFY)",
         ceo_identification_status="How the CEO was identified", ceo_strict_sample="1 = unique currentCEO flag in firm-year (strict sample)",
         ceo_flag_with_former_rolecode="CEO flag but role codes include FO/R", ceo_has_grants="1 if CEO has >=1 grant in GPBA that year")
write_dta(E, "ESG_CEO_Firm_Year.dta", L, log, keys=fyk + ["participantid"])
