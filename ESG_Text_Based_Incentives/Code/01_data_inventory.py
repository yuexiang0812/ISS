"""Step 01 — Raw data inventory: every file, row/column counts, candidate keys, missing codes.
Output: Documentation/data_inventory_files.csv, Documentation/data_inventory_fields.csv, Logs/01_data_inventory.log
"""
import numpy as np, pandas as pd
from config import RAW, DOCS, get_logger

log = get_logger("01_data_inventory")
CANDIDATE_KEYS = {
    "05. Company Data by Fiscal Year.dta": [["CIK", "fiscalYear"], ["CIK", "fiscalYear", "fiscalMonth"]],
    "12. Participant Data by Fiscal Year.dta": [["CIK", "FiscalYear", "participantid"], ["CIK", "FiscalYear", "FiscalMonth", "participantid"]],
    "08. Grants of Plan-Based Awards Table.dta": [["grantID"], ["grantID", "participantid"]],
    "02. Absolute Performance Goals Data.dta": [["absId"], ["absId", "periodID"], ["grantId", "absId", "periodID"]],
    "16. Relative Performance Goals Data.dta": [["relId"], ["relId", "periodId"], ["grantId", "relId", "periodId"]],
    "03. Accelerated Performance Goals Data.dta": [["accId"], ["grantId", "accId", "periodId"]],
    "18. Summary Compensation Table.dta": [["CIK", "FiscalYear", "FiscalMonth"]],
}
files, fields = [], []
for p in sorted(RAW.glob("*.dta")):
    d = pd.read_stata(p)
    rec = dict(file=p.name, rows=len(d), cols=d.shape[1], size_mb=round(p.stat().st_size / 1e6, 1))
    for keys in CANDIDATE_KEYS.get(p.name, []):
        if all(k in d.columns for k in keys):
            rec["dup_" + "+".join(keys)] = int(d.duplicated(keys).sum())
    yc = [c for c in d.columns if c.lower() == "fiscalyear"]
    if yc:
        rec["fy_min"], rec["fy_max"] = d[yc[0]].min(), d[yc[0]].max()
    files.append(rec)
    for c in d.columns:
        s = d[c]
        r = dict(file=p.name, field=c, dtype=str(s.dtype), non_null=int(s.notna().sum()), n_unique=int(s.nunique()))
        if pd.api.types.is_numeric_dtype(s):
            r["n_missing_code_le_-9999"] = int((s <= -9999).sum()); r["min"] = s.min(); r["max"] = s.max()
        elif pd.api.types.is_datetime64_any_dtype(s):
            r["n_missing_date_code"] = int((s.dt.year >= 9000).sum()); r["min"] = s.min(); r["max"] = s.max()
        else:
            r["n_blank"] = int(s.fillna("").astype(str).str.strip().eq("").sum())
        fields.append(r)
    log.info(f"{p.name}: {rec}")
pd.DataFrame(files).to_csv(DOCS / "data_inventory_files.csv", index=False)
pd.DataFrame(fields).to_csv(DOCS / "data_inventory_fields.csv", index=False)
log.info("non-.dta files: " + ", ".join(x.name for x in RAW.iterdir() if x.suffix != ".dta"))
