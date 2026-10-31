"""Keyword matching shared by both dictionaries: case-insensitive, whole-token (alphanumeric boundaries)."""
import re
APOS = str.maketrans({"’": "'", "‘": "'"})

def kw_regex(kw: str, case_sensitive: bool = False) -> re.Pattern:
    k = re.escape(kw.translate(APOS)).replace(r"\ ", r"[\s\-/]+")  # multiword: allow space/hyphen/slash
    return re.compile(r"(?<![A-Za-z0-9])" + k + r"(?![A-Za-z0-9])", 0 if case_sensitive else re.I)

def match_terms(texts, keywords, case_sensitive=False):
    """Return list (per text) of matched keywords."""
    pats = [(kw, kw_regex(kw, case_sensitive)) for kw in keywords]
    out = []
    for t in texts:
        t = (t or "").translate(APOS)
        out.append([kw for kw, p in pats if p.search(t)] if t else [])
    return out
