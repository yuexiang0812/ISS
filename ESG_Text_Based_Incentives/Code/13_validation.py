"""Step 13 — Independent validation and human-review package.

中文说明：独立验证与人工复核材料。
A. 验证样本在 v1.0 规则冻结后抽取（种子固定）、永不重抽；任何后续版本都在同一概率样本上评估。样本定义以不含 ISS 原文的
   ID 清单形式保存（validation_sample_v1.0_ids.csv，可推送、可复现）；含原文的答案键与盲编码表仅存本地。
B. 两名编码员独立盲编码 -> 若两份编码都存在但尚无裁定文件，自动生成“待裁定表”（一致项已预填）。
C. 复核队列（不属于验证样本）：高频未知 / 规则冲突文本，用于下一版本改进。
D. 评分：只有存在裁定后的人工标签才计算 Precision / Recall / F1 / 误判率 / 漏判率 / 未知率；按时期、维度、频次分组；
   使用分层权重（单元层与目标记录层），95% 置信区间用分层自助法；同时给出编码员一致率与 Cohen's kappa。
   当前版本与 v1.0 的模型标签都会被评估。没有人工标签时绝不输出任何准确率。

A. Sample design (drawn AFTER v1.0 rules were frozen; seed fixed; never redrawn):
   population = classification units with informative text (structured-context blank units excluded);
   strata = period of use (pre2018_only / post2018_only / both) x v1.0 predicted class (strict / ext_only / non_esg / unknown)
            x frequency band (1 / 2-9 / 10+ goal rows). Each unit sampled at most once (no repeated descriptions);
   weights w = N_h / n_h (unit level) and w x n_goal_rows (goal-record level). Strata are defined by v1.0 labels, which is a
   fixed design variable, so the sample remains a valid probability sample for evaluating any later version.
"""
import hashlib, json, os
import numpy as np, pandas as pd
from config import INTER, VALID, CODE, CLASSIFIER_VERSION, SAMPLE_VERSION, get_logger
from humanlabels import load_adjudicated, load_coders, DIMS
from classify import text_id_for

log = get_logger("13_validation")
V = CLASSIFIER_VERSION
HL = VALID / "human_labels"; HL.mkdir(exist_ok=True)
A = pd.read_parquet(INTER / "dataset_A.parquet")
rules_hash = hashlib.md5((CODE / "esg_rules.py").read_bytes() + (CODE / "classify.py").read_bytes()).hexdigest()
KEY = VALID / f"validation_sample_{SAMPLE_VERSION}_KEY_local.csv"
IDS = VALID / f"validation_sample_{SAMPLE_VERSION}_ids.csv"

# ---------------- A. load (or, only for a brand-new project, draw) the frozen sample
if KEY.exists():
    S = pd.read_csv(KEY)
    if "text_key" not in S.columns:
        raise SystemExit("frozen KEY file lacks text_key; cannot link to current units")
    S["text_id_stable"] = S.text_key.map(text_id_for)
    log.info(f"frozen {SAMPLE_VERSION} sample re-used: {len(S)} units (never redrawn)")
elif IDS.exists():
    S = pd.read_csv(IDS).merge(A[["text_id", "text_key"]].rename(columns={"text_id": "text_id_stable"}), on="text_id_stable", how="left")
    assert S.text_key.notna().all(), "sample ids not found in current units (raw data changed?)"
    # the id list stores the frozen v1.0 predictions as esg_*_v1.0; the KEY layout stores them as esg_*_model
    S = S.rename(columns={f"{d}_{SAMPLE_VERSION}": f"{d}_model" for d in DIMS})
    if f"text_id_{SAMPLE_VERSION}" in S.columns:
        S["text_id"] = S[f"text_id_{SAMPLE_VERSION}"]
    log.info(f"frozen {SAMPLE_VERSION} sample rebuilt from id list: {len(S)} units")
elif os.environ.get("ESG_DRAW_NEW_SAMPLE") != "1":
    raise SystemExit(f"frozen validation sample not found ({KEY.name} / {IDS.name}). The sample is never redrawn; restore the id list "
                     "from git. Only for a brand-new project set ESG_DRAW_NEW_SAMPLE=1.")
else:
    pop = A[A.classification_method_model != "structured_context"].copy()
    pop["period"] = np.select([pop.last_year < 2018, pop.first_year >= 2018], ["pre2018_only", "post2018_only"], "both")
    pop["pred"] = np.select([pop.esg_strict_model == 1, pop.esg_extended_model == 1, pop.esg_strict_model == 0], ["strict", "ext_only", "non_esg"], "unknown")
    pop["freq"] = pd.cut(pop.n_goal_rows, [0, 1, 9, 10**9], labels=["f1", "f2_9", "f10p"]).astype(str)
    pop["stratum"] = pop.period + "|" + pop.pred + "|" + pop.freq
    ALLOC = {"strict": 25, "ext_only": 14, "non_esg": 25, "unknown": 15}
    rng = np.random.default_rng(20261031)
    parts = [d.iloc[rng.choice(len(d), size=min(len(d), ALLOC[d.pred.iat[0]]), replace=False)].assign(N_h=len(d), n_h=min(len(d), ALLOC[d.pred.iat[0]]))
             for h, d in pop.groupby("stratum")]
    S = pd.concat(parts).sample(frac=1, random_state=7).reset_index(drop=True)
    S["w_unit"] = S.N_h / S.n_h
    S.insert(0, "sample_id", [f"V{i:04d}" for i in range(1, len(S) + 1)])
    S = S.rename(columns={"text_id": "text_id_stable"})
    S["rules_md5"] = rules_hash; S["classifier_version"] = V
    S.to_csv(KEY, index=False)
    log.info(f"NEW validation sample drawn: {len(S)} units")
# pushable id list (no ISS text): reproduces the sample from raw data
S[["sample_id", "text_id_stable"] + (["text_id"] if "text_id" in S.columns else []) + ["stratum", "period", "pred", "freq", "N_h", "n_h", "w_unit", "n_goal_rows",
   "esg_strict_model", "esg_extended_model", "esg_e_model", "esg_s_model", "esg_g_model"]].rename(
    columns={**{c: c.replace("_model", f"_{SAMPLE_VERSION}") for c in ["esg_strict_model", "esg_extended_model", "esg_e_model", "esg_s_model", "esg_g_model"]},
             "text_id": f"text_id_{SAMPLE_VERSION}"}
).to_csv(IDS, index=False)
# blind coding sheets: created once, never overwritten (coders may already be working on them)
for coder in ["coder1", "coder2"]:
    p = VALID / f"validation_coding_sheet_{SAMPLE_VERSION}_{coder}_local.csv"
    if not p.exists():
        blind = S[["sample_id", "text_key"]].merge(A[["text_key", "metric", "text_original", "first_year", "last_year", "n_firms"]],
                                                   on="text_key", how="left")
        for c in ["h_esg_strict", "h_esg_extended", "h_esg_e", "h_esg_s", "h_esg_g", "h_confidence", "h_notes", "coder_id"]:
            blind[c] = ""
        blind.drop(columns=["text_key"]).to_csv(p, index=False)
log.info("sample by period x v1.0 predicted class:\n" + S.groupby(["period", "pred"]).size().unstack().to_string())

# ---------------- C. human review queue (separate from validation; excludes sampled units)
q = A[(A.review_priority != "") & ~A.text_key.isin(S.text_key)].sort_values("n_goal_rows", ascending=False)
q[["text_id", "text_key", "metric", "text_original", "review_priority", "esg_strict", "esg_extended", "classification_reason", "n_goal_rows",
   "first_year", "last_year"]].head(1500).to_csv(VALID / f"human_review_queue_{V}_local.csv", index=False)
log.info(f"human review queue: {min(len(q), 1500)} units (of {len(q)} flagged)")


# ---------------- D. scoring
def metrics(d, pred, ref, w):
    """Weighted confusion metrics. Units whose human reference is Unknown are excluded from accuracy metrics; a model
    Unknown counts as 'not 1' for recall/FNR and is excluded from FPR's denominator (not a confident 0)."""
    d = d[d[ref].notna()]
    W = d[w]
    TP = (W * ((d[pred] == 1) & (d[ref] == 1))).sum(); FP = (W * ((d[pred] == 1) & (d[ref] == 0))).sum()
    FN = (W * ((d[pred] != 1) & (d[ref] == 1))).sum(); TN = (W * ((d[pred] == 0) & (d[ref] == 0))).sum()
    P = TP / (TP + FP) if (TP + FP) > 0 else np.nan
    Rc = TP / (TP + FN) if (TP + FN) > 0 else np.nan
    F1 = 2 * P * Rc / (P + Rc) if (np.isfinite(P) and np.isfinite(Rc) and (P + Rc) > 0) else np.nan
    return dict(precision=P, recall=Rc, f1=F1, fpr=FP / (FP + TN) if (FP + TN) > 0 else np.nan,
                fnr=FN / (TP + FN) if (TP + FN) > 0 else np.nan,
                model_unknown_rate=float((W * d[pred].isna()).sum() / W.sum()) if W.sum() > 0 else np.nan,
                n_units=int(len(d)))


def stratified_boot(d, pred, ref, w, B, rng):
    out = []
    groups = [g for _, g in d.groupby("stratum")]
    for _ in range(B):
        bs = pd.concat([g.iloc[rng.integers(0, len(g), len(g))] for g in groups])
        out.append(metrics(bs, pred, ref, w))
    return out


def kappa(a, b):
    a, b = a.fillna(-1), b.fillna(-1)          # Unknown is its own category
    po = (a == b).mean(); cats = set(a) | set(b)
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return po, (po - pe) / (1 - pe) if pe < 1 else np.nan


coders = load_coders(A)
H = load_adjudicated(A)
status = {}
if len(coders) >= 2:
    (n1, c1), (n2, c2) = coders[:2]
    j = c1[["text_key"] + [f"h_{d}" for d in DIMS]].merge(c2[["text_key"] + [f"h_{d}" for d in DIMS]], on="text_key", suffixes=("_1", "_2"))
    for d in DIMS:
        po, k = kappa(j[f"h_{d}_1"], j[f"h_{d}_2"])
        status[f"intercoder_{d}"] = dict(agreement=round(po, 4), cohen_kappa=round(k, 4) if np.isfinite(k) else None, n=len(j))
    log.info(f"inter-coder agreement: {status}")
    if H is None:   # adjudication helper
        adjs = j.copy()
        for d in DIMS:
            agree = (adjs[f"h_{d}_1"].fillna(-1) == adjs[f"h_{d}_2"].fillna(-1))
            adjs[f"human_{d}"] = np.where(agree, adjs[f"h_{d}_1"].map(lambda v: "U" if pd.isna(v) else str(int(v))), "")
            adjs[f"disagree_{d}"] = (~agree).astype(int)
        adjs = adjs.merge(S[["sample_id", "text_key"]], on="text_key", how="left").merge(A[["text_key", "text_original"]], on="text_key", how="left")
        adjs.to_csv(VALID / "human_labels" / "adjudication_sheet_local.csv", index=False)
        log.info("adjudication sheet written (agreements prefilled); save the completed file as human_labels/adjudicated_labels.csv")

if H is None:
    msg = ("NO ADJUDICATED HUMAN LABELS: classification performance is NOT validated; all labels are provisional. "
           f"Two coders code the blind sheets ({len(S)} units, Validation/validation_coding_sheet_{SAMPLE_VERSION}_coder*_local.csv), "
           "save them as Validation/human_labels/coder1_labels.csv and coder2_labels.csv, adjudicate disagreements into "
           "Validation/human_labels/adjudicated_labels.csv (values 1/0/U), then run: python master_run.py 06")
    (VALID / f"validation_status_{V}.json").write_text(json.dumps(dict(status="pending_human_labels", classifier_version=V,
                                                                         sample_version=SAMPLE_VERSION, n_sample=len(S), message=msg,
                                                                         rules_md5=rules_hash, **status), indent=2))
    log.info(msg)
else:
    E = S.merge(H[["text_key"] + [f"human_{d}" for d in DIMS]], on="text_key", how="inner")
    cur = A[["text_key", "esg_strict_model", "esg_extended_model", "esg_e_model", "esg_s_model", "esg_g_model"]]
    E = E.drop(columns=[c for c in E.columns if c.endswith("_model")]).merge(cur, on="text_key", how="left")
    v10 = pd.read_csv(IDS)[["sample_id"] + [f"{x}_{SAMPLE_VERSION}" for x in DIMS]]
    E = E.merge(v10, on="sample_id", how="left")
    E["w_row"] = E.w_unit * E.n_goal_rows
    rng = np.random.default_rng(1)
    rows = []
    for ver, suffix in [(V, "_model"), (SAMPLE_VERSION, f"_{SAMPLE_VERSION}")]:
        for dim in DIMS:
            pred, ref = f"{dim}{suffix}", f"human_{dim}"
            for grp, d in [("all", E)] + [(f"period={k}", g) for k, g in E.groupby("period")] + [(f"freq={k}", g) for k, g in E.groupby("freq")]:
                for wname in ["w_unit", "w_row"]:
                    m = metrics(d, pred, ref, wname)
                    boot = stratified_boot(d, pred, ref, wname, 300, rng)
                    for k_, v_ in m.items():
                        if k_ == "n_units":
                            continue
                        vals = np.array([b[k_] for b in boot], dtype=float)
                        rows.append(dict(classifier_version=ver, dimension=dim, group=grp, weight=wname, metric=k_, estimate=v_,
                                         ci_low=np.nanpercentile(vals, 2.5) if np.isfinite(vals).any() else np.nan,
                                         ci_high=np.nanpercentile(vals, 97.5) if np.isfinite(vals).any() else np.nan, n_units=m["n_units"]))
    M = pd.DataFrame(rows)
    M.to_csv(VALID / f"validation_metrics_{V}.csv", index=False)
    (VALID / f"validation_status_{V}.json").write_text(json.dumps(dict(status="validated_against_human_labels", classifier_version=V,
                                                                         sample_version=SAMPLE_VERSION, n_labelled=int(len(E)), **status), indent=2))
    log.info("validation metrics (all units, unit weights):\n" + M[(M.group == "all") & (M.weight == "w_unit")].pivot_table(
        index=["classifier_version", "dimension"], columns="metric", values="estimate").round(3).to_string())
