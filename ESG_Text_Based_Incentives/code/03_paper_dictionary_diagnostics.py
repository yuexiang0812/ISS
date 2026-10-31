"""Apply the AGHJ (2025) 953-term dictionary literally to metricOther and diagnose every keyword.

Paper implementation (Section 3.2): a metric is ESG if its `metricother` text contains a keyword.
The paper does not state the matching rule; we use case-insensitive whole-token matching (the
most literal reading). ISS ESG flags are attached ONLY as diagnostics.
"""
import pandas as pd
from config import DICT, INTER, ISS_ESG_METRICTYPES, ISS_2018_ESG_METRIC_LABELS
from textmatch import match_terms

kd = pd.read_csv(DICT / "a_paper_dictionary_AGHJ2025_953.csv")
k = pd.read_parquet(INTER / "kpi_text_all.parquet")
k["iss_esg"] = k.metricType.isin(ISS_ESG_METRICTYPES) | k.metric.isin(ISS_2018_ESG_METRIC_LABELS)
u = pd.read_parquet(INTER / "unique_texts.parquet")
u["paper_terms"] = match_terms(u.metricOther_norm.tolist(), kd.keyword.tolist())
u["paper_esg"] = u.paper_terms.str.len() > 0
u.to_parquet(INTER / "unique_texts_paper.parquet", index=False)

k = k.merge(u[["text_id", "paper_terms"]], on="text_id")
post = k.fiscalYear >= 2018
ex = k[k.paper_terms.str.len() > 0].explode("paper_terms")
rows = []
for kw, d in ex.groupby("paper_terms"):
    dp = d[d.fiscalYear >= 2018]
    top = d.groupby("metricOther_norm").size().sort_values(ascending=False)
    nonis = dp[~dp.iss_esg].groupby("metricOther_norm").size().sort_values(ascending=False)
    rows.append(dict(keyword=kw, n_texts=d.text_id.nunique(), n_kpi=len(d), n_kpi_pre2018=int((d.fiscalYear < 2018).sum()),
                     n_kpi_post2018=len(dp), iss_esg_share_post2018=round(dp.iss_esg.mean(), 3) if len(dp) else None,
                     only_keyword_in_text=int((d.paper_terms.map(lambda x: True)).sum()),
                     top_texts=" | ".join(top.index[:8]), top_post2018_non_iss_texts=" | ".join(nonis.index[:6])))
diag = kd[["kw_id", "keyword", "source_page"]].merge(pd.DataFrame(rows).drop(columns="only_keyword_in_text"), on="keyword", how="left")
diag[["n_texts", "n_kpi", "n_kpi_pre2018", "n_kpi_post2018"]] = diag[["n_texts", "n_kpi", "n_kpi_pre2018", "n_kpi_post2018"]].fillna(0).astype(int)
diag.to_csv(DICT / "diagnostics_paper_keywords.csv", index=False)
print(f"keywords with >=1 match: {(diag.n_kpi > 0).sum()} of 953")
print(f"unique texts matched: {u.paper_esg.sum():,} of {len(u):,}")
