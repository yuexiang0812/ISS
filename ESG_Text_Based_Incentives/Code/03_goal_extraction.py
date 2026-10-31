"""Step 03 — Goal extraction: stack absolute / relative / accelerated performance-goal records.

Unit (raw goal record) = one objective x one measurement period within a grant.
True row key = (goal_source, grantId, goal_id, periodId): goal ids (absId/relId) are recycled across
grants, so they are NOT unique on their own (verified below).
Grant attributes (CIK, participant, fiscal year/month, award type) are attached from the grants table.
"""
import re, unicodedata
import numpy as np, pandas as pd
from config import (INTER, GOAL_FILES, ISS_2018_ESG_METRIC_LABELS, ISS_ESG_METRICTYPES,
                    read_raw, clean_missing_codes, get_logger, check_unique)

log = get_logger("03_goal_extraction")
KEEP = ["fiscalYear", "grantId", "metricType", "metric", "metricOther", "percentVest", "vestLow", "vestHigh",
        "goalThreshold", "goalTarget", "goalMax", "payoutTarget"]
EXTRA = {"REL": ["relativeBenchmark", "compareMethod"], "ACC": ["relativeBenchmark", "compareMethod", "contingencyType"]}

frames = []
for src, (fk, oid, pid) in GOAL_FILES.items():
    d = read_raw(fk, columns=KEEP + [oid, pid] + EXTRA.get(src, []))
    d = d.rename(columns={oid: "goal_id", pid: "periodId"}); d.insert(0, "goal_source", src)
    log.info(f"{src}: {len(d):,} rows | goal ids unique alone: {d.goal_id.is_unique} | "
             f"dup(goal_id, period) = {d.duplicated(['goal_id','periodId']).sum():,} | grants = {d.grantId.nunique():,}")
    check_unique(d, ["grantId", "goal_id", "periodId"], f"{src} goal records", log)
    frames.append(d)
k = pd.concat(frames, ignore_index=True)
for c in ["metricType", "metric", "metricOther", "relativeBenchmark", "compareMethod", "contingencyType"]:
    k[c] = k[c].fillna("").astype(str).str.strip()
for c in ["percentVest", "vestLow", "vestHigh", "goalThreshold", "goalTarget", "goalMax", "payoutTarget"]:
    raw = pd.to_numeric(k[c], errors="coerce")
    k[c + "_missing_code"] = (raw <= -9999).astype("int8")
    k[c] = clean_missing_codes(raw)
k["periodId"] = k.periodId.fillna(-1).astype("int64")
k["goal_record_id"] = (k.goal_source + "_" + k.grantId.astype("int64").astype(str) + "_" +
                       k.goal_id.astype("int64").astype(str) + "_" + k.periodId.astype(str))
check_unique(k, ["goal_record_id"], "stacked goal records", log)

g = read_raw("grant", columns=["grantID", "CIK", "FiscalYear", "FiscalMonth", "participantid", "AwardType", "performancetype"])
dups = g[g.grantID.duplicated(keep=False)]
log.info(f"grants table: {len(g):,} rows; duplicated grantID rows {len(dups)}; conflicting attributes within dup ids: "
         f"{int(dups.groupby('grantID')[['CIK','participantid','FiscalYear','FiscalMonth','AwardType']].nunique().gt(1).any(axis=1).sum())}")
g = g.drop_duplicates("grantID").rename(columns={"grantID": "grantId", "FiscalYear": "grant_fy", "FiscalMonth": "fiscalMonth",
                                                 "participantid": "participantId"})
k = k.merge(g, on="grantId", how="left", validate="m:1", indicator=True)
k["goal_grant_matched"] = (k.pop("_merge") == "both").astype("int8")
log.info(f"goal records matched to a grant: {k.goal_grant_matched.mean():.4%} (unmatched {int((k.goal_grant_matched==0).sum())})")
m = k.goal_grant_matched == 1
log.info(f"goal fiscalYear == grant FiscalYear (matched): {(k.fiscalYear[m] == k.grant_fy[m]).mean():.4%}")


def norm(s: str) -> str:
    s = s.replace("‚Äô", "'").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".;, ").strip()
    return s
k["metricOther_norm"] = k.metricOther.map(norm)
k["iss_esg_flag"] = (k.metricType.isin(ISS_ESG_METRICTYPES) | k.metric.isin(ISS_2018_ESG_METRIC_LABELS)).astype("int8")

span = k.groupby("metric").fiscalYear.agg(["min", "max", "size"]).sort_values("min")
log.info("`metric` label first/last fiscal year:\n" + span.to_string())
log.info(f"2018-taxonomy ESG `metric` labels before 2018: {int((k.metric.isin(ISS_2018_ESG_METRIC_LABELS) & (k.fiscalYear < 2018)).sum())} "
         f"of {int(k.metric.isin(ISS_2018_ESG_METRIC_LABELS).sum()):,}")
log.info("metricOther blank share by year:\n" + k.groupby("fiscalYear").metricOther_norm.apply(lambda s: (s == "").mean()).round(3).to_string())
log.info("metricType by year:\n" + pd.crosstab(k.fiscalYear, k.metricType).to_string())
k.to_parquet(INTER / "goal_records.parquet", index=False)
log.info(f"saved {len(k):,} goal records")
