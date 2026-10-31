"""Helpers: tri-state aggregation and labelled Stata (.dta) export."""
import json
import numpy as np, pandas as pd
from config import FINAL, INTER

ABBREV = [("_extended", "_ext"), ("compensation", "comp"), ("classification", "class"), ("_strict", "_str")]


def stata_name(name: str) -> str:
    """Stata names <= 32 chars. Overlong preferred names are shortened by a fixed, documented rule."""
    n = name
    for a, b in ABBREV:
        if len(n) <= 32:
            break
        n = n.replace(a, b)
    assert len(n) <= 32, name
    return n


def tri_any(values):
    """Adoption logic on a list of 1/0/NaN: 1 if any 1; 0 if all 0 (and non-empty); NaN otherwise."""
    v = pd.Series(values, dtype="float")
    if (v == 1).any():
        return 1.0
    if len(v) and (v == 0).all():
        return 0.0
    return np.nan


def agg_tri(df, by, col):
    """Vectorised tri_any by group -> Series (1 if any 1; 0 if all 0; NaN otherwise)."""
    t = df.assign(_p=(df[col] == 1).astype("int32"), _z=(df[col] == 0).astype("int32"), _n=1).groupby(by)[["_p", "_z", "_n"]].sum()
    return pd.Series(np.where(t._p > 0, 1.0, np.where(t._z == t._n, 0.0, np.nan)), index=t.index)


def share_block(n_pos, n_unknown, n_total):
    """Exact share only when complete; lower/upper bounds always (NaN when denominator is 0)."""
    n_pos, n_unknown, n_total = (pd.Series(x, dtype="float") if not isinstance(x, pd.Series) else x.astype(float) for x in (n_pos, n_unknown, n_total))
    with np.errstate(divide="ignore", invalid="ignore"):
        lb = np.where(n_total > 0, n_pos / n_total, np.nan)
        ub = np.where(n_total > 0, (n_pos + n_unknown) / n_total, np.nan)
        exact = np.where((n_total > 0) & (n_unknown == 0), n_pos / n_total, np.nan)
        cov = np.where(n_total > 0, (n_total - n_unknown) / n_total, np.nan)
    return exact, lb, ub, cov


NAME_MAP = {}


def write_dta(df: pd.DataFrame, filename: str, labels: dict, log, keys=None):
    """Write labelled .dta (Stata 118). Strings sanitised; tri-state vars stay float with '.' = Unknown/NA."""
    out = df.copy()
    ren = {c: stata_name(c) for c in out.columns}
    out = out.rename(columns=ren)
    for pref, st in ren.items():
        NAME_MAP[(filename, st)] = pref
    vl = {}
    for c in out.columns:
        pref = {v: k for k, v in ren.items()}[c]
        vl[c] = (labels.get(pref) or pref)[:80]
        s = out[c]
        if pd.api.types.is_bool_dtype(s):
            out[c] = s.astype("int8")
        elif pd.api.types.is_datetime64_any_dtype(s):
            pass
        elif s.dtype == object or pd.api.types.is_string_dtype(s):
            out[c] = s.fillna("").astype(str).str.encode("latin-1", "replace").str.decode("latin-1")
    if keys:
        k = [ren[x] for x in keys]
        assert not out.duplicated(k).any(), f"{filename}: duplicate primary key {keys}"
        assert out[k].notna().all().all(), f"{filename}: missing primary key values"
    path = FINAL / filename
    out.to_stata(path, write_index=False, version=118, variable_labels=vl,
                 convert_strl=[c for c in out.columns if out[c].dtype == object and out[c].str.len().max() > 2000])
    log.info(f"[dta] {filename}: {len(out):,} obs x {out.shape[1]} vars; key={keys}; renamed(overlong)="
             f"{ {k: v for k, v in ren.items() if k != v} }")
    pd.DataFrame([(filename, st, p, vl[st]) for (f, st), p in NAME_MAP.items() if f == filename],
                 columns=["dataset", "stata_name", "preferred_name", "label"]).to_csv(INTER / f"varmap_{filename}.csv", index=False)
    return path
