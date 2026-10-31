"""Step 13 — Independent validation of the frozen classifier (v1.0) and human-review package.

A. Sample design (drawn AFTER rules were frozen; seed fixed):
   population = classification units (Dataset A) with informative text (structured-context blank units excluded),
   strata = period of use (pre2018_only / post2018_only / both) x predicted Strict class (1 / extended-only / 0 / unknown)
            x frequency band (1 row / 2-9 rows / 10+ rows).
   Each unit is sampled at most once, so repeated occurrences of the same description are not double counted;
   population-level estimates use stratum weights w = N_h / n_h (unit-level) and w * n_goal_rows (row-level).
B. Blind coding sheet (no model labels) for two independent coders + adjudication; separate answer key.
C. Human review queue (NOT validation): frequent unresolved / flagged units, to resolve Unknowns in v1.1.
D. Scoring (runs only when coder files exist in Validation/human_labels/): precision, recall, F1, FPR, FNR,
   unknown rate, by period / dimension / frequency, stratum-weighted, 95% bootstrap CIs over units; Cohen's kappa.
   Without human labels NO accuracy statistic is produced.
"""
import hashlib, json
import numpy as np, pandas as pd
from config import INTER, VALID, CODE, CLASSIFIER_VERSION, get_logger

log = get_logger("13_validation")
V = CLASSIFIER_VERSION
HL = VALID / "human_labels"; HL.mkdir(exist_ok=True)
A = pd.read_parquet(INTER / "dataset_A.parquet")
rules_hash = hashlib.md5((CODE / "esg_rules.py").read_bytes() + (CODE / "classify.py").read_bytes()).hexdigest()

pop = A[A.classification_method_model != "structured_context"].copy()
pop["period"] = np.select([pop.last_year < 2018, pop.first_year >= 2018], ["pre2018_only", "post2018_only"], "both")
pop["pred"] = np.select([pop.esg_strict_model == 1, pop.esg_extended_model == 1, pop.esg_strict_model == 0], ["strict", "ext_only", "non_esg"], "unknown")
pop["freq"] = pd.cut(pop.n_goal_rows, [0, 1, 9, 10**9], labels=["f1", "f2_9", "f10p"]).astype(str)
pop["stratum"] = pop.period + "|" + pop.pred + "|" + pop.freq
ALLOC = {"strict": 25, "ext_only": 14, "non_esg": 25, "unknown": 15}       # per (period x freq) cell
sample_path = VALID / f"validation_sample_{V}_KEY_local.csv"
if sample_path.exists():
    S = pd.read_csv(sample_path)
    log.info(f"existing frozen sample re-used ({len(S)} units) — never redrawn after coding starts")
else:
    rng = np.random.default_rng(20261031)
    parts = []
    for h, d in pop.groupby("stratum"):
        n = min(len(d), ALLOC[d.pred.iat[0]])
        parts.append(d.iloc[rng.choice(len(d), size=n, replace=False)].assign(N_h=len(d), n_h=n))
    S = pd.concat(parts)
    S["w_unit"] = S.N_h / S.n_h
    S = S.sample(frac=1, random_state=7).reset_index(drop=True)
    S.insert(0, "sample_id", [f"V{i:04d}" for i in range(1, len(S) + 1)])
    S["rules_md5"] = rules_hash; S["classifier_version"] = V
    S[["sample_id", "text_id", "stratum", "period", "pred", "freq", "N_h", "n_h", "w_unit", "n_goal_rows", "n_rows_pre2018",
       "esg_strict_model", "esg_extended_model", "esg_e_model", "esg_s_model", "esg_g_model", "paper_esg_as_used", "rules_md5",
       "classifier_version"]].to_csv(sample_path, index=False)
    blind = S[["sample_id", "text_id", "metric", "text_original", "first_year", "last_year", "n_firms"]].copy()
    for c in ["h_esg_strict", "h_esg_extended", "h_esg_e", "h_esg_s", "h_esg_g", "h_confidence", "h_notes", "coder_id"]:
        blind[c] = ""
    for coder in ["coder1", "coder2"]:
        blind.to_csv(VALID / f"validation_coding_sheet_{V}_{coder}_local.csv", index=False)
    log.info(f"validation sample drawn: {len(S)} units in {S.stratum.nunique()} strata; rules md5 {rules_hash}")
log.info("sample by stratum:\n" + S.groupby(["period", "pred"]).size().unstack().to_string())

# ---- C. human review queue (separate from validation; excludes sampled units)
q = A[(A.review_priority != "") & ~A.text_id.isin(S.text_id)].sort_values("n_goal_rows", ascending=False)
q[["text_id", "metric", "text_original", "review_priority", "esg_strict", "esg_extended", "classification_reason", "n_goal_rows",
   "first_year", "last_year"]].head(1500).to_csv(VALID / f"human_review_queue_{V}_local.csv", index=False)
log.info(f"human review queue: {min(len(q),1500)} units (of {len(q)} flagged)")

# ---- D. scoring
coder_files = sorted(HL.glob("coder*_labels.csv"))
adj = HL / "adjudicated_labels.csv"
if not adj.exists():
    msg = ("NO HUMAN LABELS AVAILABLE: classification performance is NOT validated. All labels are provisional. "
           f"Code the blind sheets ({len(S)} units), place them in Validation/human_labels/ as coder1_labels.csv / coder2_labels.csv, "
           "adjudicate disagreements into adjudicated_labels.csv, then re-run this step.")
    (VALID / f"validation_status_{V}.json").write_text(json.dumps(dict(status="pending_human_labels", n_sample=len(S), message=msg,
                                                                         rules_md5=rules_hash), indent=2))
    log.info(msg)
else:
    H = pd.read_csv(adj).merge(S, on="text_id", how="inner")
    rng = np.random.default_rng(1)
    def metrics(df, pred, ref, w):
        d = df[[pred, ref, w]].copy(); d = d[d[ref].notna()]
        tp = (w_ := d[w]) * ((d[pred] == 1) & (d[ref] == 1)); fp = w_ * ((d[pred] == 1) & (d[ref] == 0))
        fn = w_ * ((d[pred] != 1) & (d[ref] == 1)); tn = w_ * ((d[pred] == 0) & (d[ref] == 0))
        TP, FP, FN, TN = tp.sum(), fp.sum(), fn.sum(), tn.sum()
        P = TP / (TP + FP) if TP + FP else np.nan; R = TP / (TP + FN) if TP + FN else np.nan
        return dict(precision=P, recall=R, f1=2 * P * R / (P + R) if P and R else np.nan, fpr=FP / (FP + TN) if FP + TN else np.nan,
                    fnr=FN / (TP + FN) if TP + FN else np.nan, pred_unknown_rate=float((w_ * d[pred].isna()).sum() / w_.sum()))
    H["w_row"] = H.w_unit * H.n_goal_rows
    rows = []
    for dim, pred, ref in [("strict", "esg_strict_model", "human_esg_strict"), ("extended", "esg_extended_model", "human_esg_extended"),
                           ("E", "esg_e_model", "human_esg_e"), ("S", "esg_s_model", "human_esg_s"), ("G", "esg_g_model", "human_esg_g")]:
        for grp, d in [("all", H)] + list(H.groupby("period")) + list(H.groupby("freq")):
            for wname in ["w_unit", "w_row"]:
                m = metrics(d, pred, ref, wname)
                boot = [metrics(d.iloc[rng.integers(0, len(d), len(d))], pred, ref, wname) for _ in range(500)]
                for k in m:
                    vals = np.array([b[k] for b in boot], dtype=float)
                    rows.append(dict(dimension=dim, group=grp, weight=wname, metric=k, estimate=m[k],
                                     ci_low=np.nanpercentile(vals, 2.5), ci_high=np.nanpercentile(vals, 97.5), n_units=len(d)))
    pd.DataFrame(rows).to_csv(VALID / f"validation_metrics_{V}.csv", index=False)
    if len(coder_files) >= 2:
        a, b = (pd.read_csv(f).set_index("text_id")["h_esg_strict"].astype(str) for f in coder_files[:2])
        j = a.to_frame("a").join(b.to_frame("b"), how="inner")
        po = (j.a == j.b).mean(); pe = sum((j.a == c).mean() * (j.b == c).mean() for c in set(j.a) | set(j.b))
        log.info(f"inter-coder agreement strict: {po:.3f}, Cohen's kappa {(po - pe) / (1 - pe):.3f} (n={len(j)})")
    log.info("validation metrics written")
