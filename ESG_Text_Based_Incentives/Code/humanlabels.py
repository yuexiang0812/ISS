"""Loading and normalising human labels (shared by Step 06 and Step 13).

中文说明：人工标注文件的统一读取。支持 1 / 0 / U（未知）或空白；通过 sample_id（验证样本）、text_key（复核队列）
或 text_id 三种方式定位文本，并统一换算为稳定的 text_key，使标注在分类器升级（text_id 变化）后依然有效。
人工标注若出现 Strict=1 但 Extended≠1，按定义自动改为 Extended=1 并记录。

Accepted files (Validation/human_labels/):
  adjudicated_labels.csv    final labels; columns: one of [sample_id | text_key | text_id] +
                            human_esg_strict, human_esg_extended, human_esg_e, human_esg_s, human_esg_g (+ reviewer, review_date)
  coder1_labels.csv / coder2_labels.csv   completed blind coding sheets (columns sample_id, h_esg_strict, ...)
"""
import numpy as np, pandas as pd
from config import VALID, SAMPLE_VERSION

DIMS = ["esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g"]


def parse_value(v):
    """'1'/'1.0'/1 -> 1.0 ; '0' -> 0.0 ; 'U'/'u'/''/NaN/'?' -> NaN ; anything else -> ValueError."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    s = str(v).strip().upper()
    if s in ("", "U", "UNKNOWN", "?", "NAN", "NA", "."):
        return np.nan
    if s in ("1", "1.0", "YES", "Y"):
        return 1.0
    if s in ("0", "0.0", "NO", "N"):
        return 0.0
    raise ValueError(f"unrecognised human label value: {v!r} (use 1, 0 or U)")


def sample_key():
    """Local answer key (sample_id, v1.0 text_id, text_key) or None."""
    p = VALID / f"validation_sample_{SAMPLE_VERSION}_KEY_local.csv"
    return pd.read_csv(p) if p.exists() else None


def sample_ids():
    """Pushable id list (sample_id, text_id_stable[, text_id_v1.0]) or None."""
    p = VALID / f"validation_sample_{SAMPLE_VERSION}_ids.csv"
    return pd.read_csv(p) if p.exists() else None


def _id_maps(A):
    """sample_id -> text_key and text_id (current hash or v1.0 sequential) -> text_key."""
    sid, tid = {}, {}
    if A is not None:
        tid.update(zip(A.text_id, A.text_key))
    ids = sample_ids()
    if ids is not None and A is not None:
        h2k = dict(zip(A.text_id, A.text_key))
        sid.update({s: h2k[t] for s, t in zip(ids.sample_id, ids.text_id_stable) if t in h2k})
        if f"text_id_{SAMPLE_VERSION}" in ids.columns:
            tid.update({o: h2k[t] for o, t in zip(ids[f"text_id_{SAMPLE_VERSION}"], ids.text_id_stable) if t in h2k and isinstance(o, str)})
    key = sample_key()
    if key is not None:
        sid.update(zip(key.sample_id, key.text_key))
        tid.update(zip(key.text_id, key.text_key))      # v1.0 sequential ids printed on the coding sheets
    return sid, tid


def resolve_text_key(df, A=None):
    """Add text_key, resolving each row from text_key, else sample_id, else text_id (current or v1.0 sheet id)."""
    df = df.copy()
    sid, tid = _id_maps(A)
    col = lambda c: df[c] if c in df.columns else pd.Series([np.nan] * len(df), index=df.index, dtype=object)
    tk, si, ti = col("text_key"), col("sample_id").map(sid), col("text_id").map(tid)
    df["text_key"] = tk.where(tk.notna() & (tk.astype(str) != ""), si.where(si.notna(), ti))
    if df.text_key.isna().any():
        bad = df[df.text_key.isna()].head(5).to_dict("records")
        raise ValueError(f"{int(df.text_key.isna().sum())} human-label rows could not be matched to a text unit "
                         f"(need sample_id, text_key or a text_id); first rows: {bad}")
    return df


def normalise(h, prefix):
    """Apply the label consistency rules of CODING_GUIDELINES.md; returns (frame, n_auto_fixed). Contradictions raise."""
    S, X = h[prefix + "esg_strict"], h[prefix + "esg_extended"]
    P = [prefix + f"esg_{q}" for q in "esg"]
    fix = ((S == 1) & (X != 1)) | ((X == 0) & (S != 0))
    h.loc[(S == 1) & (X != 1), prefix + "esg_extended"] = 1.0         # Strict ESG is always Extended
    h.loc[(h[prefix + "esg_extended"] == 0), prefix + "esg_strict"] = 0.0   # not Extended => not Strict
    S = h[prefix + "esg_strict"]
    contra = (h[P].eq(1).any(axis=1) & (S != 1)) | ((S == 1) & h[P].eq(0).all(axis=1))
    if contra.any():
        raise ValueError(f"{int(contra.sum())} human-label rows are contradictory (a pillar = 1 while Strict != 1, or Strict = 1 with "
                         f"E = S = G = 0): {h.loc[contra].head(5).to_dict('records')}")
    for c in P:
        h.loc[S == 0, c] = 0.0           # not ESG => no pillar
        h.loc[S.isna(), c] = np.nan      # Strict unknown => pillars unknown
    return h, fix.astype(int)


def load_adjudicated(A=None):
    """Return DataFrame [text_key, human_<dim>..., human_invariant_fixed] or None if no adjudicated file exists."""
    p = VALID / "human_labels" / "adjudicated_labels.csv"
    if not p.exists():
        return None
    h = pd.read_csv(p, dtype=str)
    for d in DIMS:
        col = "human_" + d
        h[col] = h[col].map(parse_value) if col in h.columns else np.nan
    h = resolve_text_key(h, A)
    h, nfix = normalise(h, "human_")
    h["human_invariant_fixed"] = nfix.values
    return h.drop_duplicates("text_key", keep="last")


def load_coders(A=None):
    """Return list of (name, DataFrame[text_key, h_esg_strict ...]) for completed coder sheets."""
    out = []
    for p in sorted((VALID / "human_labels").glob("coder*_labels.csv")):
        c = pd.read_csv(p, dtype=str)
        for d in DIMS:
            col = "h_" + d
            c[col] = c[col].map(parse_value) if col in c.columns else np.nan
        c = resolve_text_key(c, A)
        out.append((p.stem, normalise(c, "h_")[0]))
    return out
