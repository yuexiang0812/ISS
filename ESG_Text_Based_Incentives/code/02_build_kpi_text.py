"""Stack absolute / relative / accelerated performance-goal rows into one KPI text table.

KPI row = one goal record, keyed by (source, grantId, goal id, periodId); goal ids alone are recycled. Firm (CIK), executive (participantid) and award
type come from the grants table (08) via grantId. Raw files are only read.
Also writes the evidence used to treat ESG-specific `metric` labels as 2018 ISS taxonomy labels.
"""
import sys, unicodedata, re
import pandas as pd
from config import RAW, INTER, LOGS, GOAL_FILES, ISS_2018_ESG_METRIC_LABELS, ISS_ESG_METRICTYPES

log = open(LOGS / "02_build_kpi_text.log", "w")
def P(*a):
    print(*a); print(*a, file=log)

frames = []
for src, (fn, rid, pid) in GOAL_FILES.items():
    d = pd.read_stata(RAW / fn, columns=["fiscalYear", "grantId", rid, pid, "metricType", "metric", "metricOther"])
    d = d.rename(columns={rid: "goal_row_id", pid: "periodId"}); d.insert(0, "source", src)
    P(f"{src}: {len(d):,} rows, {d.goal_row_id.nunique():,} unique ids, {d.grantId.nunique():,} grants, "
      f"dup(goal id, period)={d.duplicated(['goal_row_id','periodId']).sum():,} -> ids are recycled across grants")
    assert not d.duplicated(["grantId", "goal_row_id", "periodId"]).any()  # true row key
    frames.append(d)
k = pd.concat(frames, ignore_index=True)
for c in ["metricType", "metric", "metricOther"]:
    k[c] = k[c].fillna("").astype(str).str.strip()
k["kpi_uid"] = (k.source + "_" + k.grantId.astype("int64").astype(str) + "_" + k.goal_row_id.astype("int64").astype(str)
                + "_" + k.periodId.fillna(-1).astype("int64").astype(str))
assert k.kpi_uid.is_unique

g = pd.read_stata(RAW / "08. Grants of Plan-Based Awards Table.dta",
                  columns=["grantID", "CIK", "FiscalYear", "participantid", "AwardType"])
g = g.rename(columns={"grantID": "grantId", "FiscalYear": "grant_fy"})
P(f"grants table: {len(g):,} rows, grantID unique={g.grantId.is_unique}")
dups = g[g.grantId.duplicated(keep=False)]
P(f"duplicate grantID rows: {len(dups)}; conflicting CIK/participant/year within dup ids: "
  f"{int(dups.groupby('grantId')[['CIK','participantid','grant_fy']].nunique().gt(1).any(axis=1).sum())}")
g = g.drop_duplicates("grantId")
k = k.merge(g, on="grantId", how="left", validate="m:1")
P(f"KPI rows matched to grants table: {k.CIK.notna().mean():.4%}")
P(f"fiscalYear == grant FiscalYear where matched: {(k.fiscalYear == k.grant_fy)[k.CIK.notna()].mean():.4%}")

def norm(s: str) -> str:
    s = s.replace("‚Äô", "'").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip()
k["metricOther_norm"] = k.metricOther.map(norm)
k["text_key"] = k.metric + " || " + k.metricOther_norm.str.lower()

# Evidence: first/last year each `metric` label appears (justifies treating 2018 ESG labels as ISS taxonomy)
span = k.groupby("metric").fiscalYear.agg(["min", "max", "size"]).sort_values("min")
P("\n`metric` label first/last fiscal year and N:\n" + span.to_string())
pre = k[k.metric.isin(ISS_2018_ESG_METRIC_LABELS) & (k.fiscalYear < 2018)]
P(f"\nRows with 2018-taxonomy ESG `metric` labels before 2018: {len(pre)} "
  f"(of {k.metric.isin(ISS_2018_ESG_METRIC_LABELS).sum():,})")
P("\nmetricOther empty share by year:\n" + k.groupby("fiscalYear").metricOther.apply(lambda s: (s == '').mean()).round(3).to_string())
P("\nISS ESG metricType by year:\n" + pd.crosstab(k.fiscalYear, k.metricType.isin(ISS_ESG_METRICTYPES)).to_string())

k.to_parquet(INTER / "kpi_text_all.parquet", index=False)
u = (k.groupby(["metric", "metricOther_norm"], dropna=False)
       .agg(n_kpi=("kpi_uid", "size"), n_grants=("grantId", "nunique"), fy_min=("fiscalYear", "min"),
            fy_max=("fiscalYear", "max"), n_pre2018=("fiscalYear", lambda s: int((s < 2018).sum())))
       .reset_index())
u.insert(0, "text_id", [f"T{i:06d}" for i in range(1, len(u) + 1)])
u.to_parquet(INTER / "unique_texts.parquet", index=False)
k = k.merge(u[["metric", "metricOther_norm", "text_id"]], on=["metric", "metricOther_norm"], how="left")
k.to_parquet(INTER / "kpi_text_all.parquet", index=False)
P(f"\nTotal KPI rows {len(k):,}; unique (metric, metricOther) texts {len(u):,}")
