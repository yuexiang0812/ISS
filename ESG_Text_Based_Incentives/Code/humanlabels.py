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
    p = VALID / f"validation_sample_{SAMPLE_VERSION}_KEY_local.csv"
    return pd.read_csv(p) if p.exists() else None


def resolve_text_key(df, A=None):
    """Add a text_key column from sample_id / text_key / text_id."""
    df = df.copy()
    if "text_key" in df.columns and df.text_key.notna().all():
        return df
    key = sample_key()
    if "sample_id" in df.columns and key is not None:
        df = df.drop(columns=["text_key"], errors="ignore").merge(key[["sample_id", "text_key"]], on="sample_id", how="left")
    elif "text_id" in df.columns and A is not None:
        df = df.merge(A[["text_id", "text_key"]], on="text_id", how="left")
    if "text_key" not in df.columns or df.text_key.isna().any():
        n = int(df.get("text_key", pd.Series([np.nan] * len(df))).isna().sum())
        raise ValueError(f"{n} human-label rows could not be matched to a text unit (need sample_id, text_key or a current text_id)")
    return df


def load_adjudicated(A=None):
    """Return DataFrame [text_key, human_<dim>...] or None if no adjudicated file exists."""
    p = VALID / "human_labels" / "adjudicated_labels.csv"
    if not p.exists():
        return None
    h = pd.read_csv(p, dtype=str)
    for d in DIMS:
        col = "human_" + d
        h[col] = h[col].map(parse_value) if col in h.columns else np.nan
    h = resolve_text_key(h, A)
    fix = (h.human_esg_strict == 1) & (h.human_esg_extended != 1)
    h.loc[fix, "human_esg_extended"] = 1.0           # definition: Strict ESG is always Extended
    h["human_invariant_fixed"] = fix.astype(int)
    return h.drop_duplicates("text_key", keep="last")


def load_coders():
    """Return list of (name, DataFrame[text_key, h_esg_strict ...]) for completed coder sheets."""
    out = []
    for p in sorted((VALID / "human_labels").glob("coder*_labels.csv")):
        c = pd.read_csv(p, dtype=str)
        for d in DIMS:
            col = "h_" + d
            c[col] = c[col].map(parse_value) if col in c.columns else np.nan
        out.append((p.stem, resolve_text_key(c)))
    return out
