"""Deterministic ESG classification engine (shared by Step 04 and validation).

Classification unit = (metric, metricOther_norm, ctx):
  * metricOther (normalized) is the primary evidence; it is read TOGETHER with `metric`
    (pre-2018 metricOther often holds only a qualifier, e.g. metric='Cashflow', metricOther='Free').
  * `metric` contributes evidence only through time-consistent standardized labels (financial labels ->
    non-ESG; 'Customer Satisfaction' -> Extended). Placeholder labels (Other/Individual/...) contribute
    nothing. 2018-taxonomy ESG labels (Staff Health And Safety, Diversity, Csr, ...) are NEVER used.
  * ctx is used only when BOTH metricOther is blank AND metric is a placeholder: the time-consistent
    financial metricType group ('Accounting', 'Stock Price' = 'Market-related', ...) is then admitted as
    structured context (classification_method = 'structured_context'); a text-only label is kept separately.
"""
import re
from esg_rules import R
from config import FIN_METRICTYPES, ISS_2018_ESG_METRIC_LABELS

FIN_LABELS = {"Sales", "EPS", "Operating Income", "Earnings", "EBITDA", "ROIC", "ROE", "Cashflow", "EBT", "Profit Margin",
              "EBIT", "EVA", "ROA", "FFO", "ROI", "Gross Revenues", "Net Income", "Tsr", "Stock Price", "Gross Profit", "Noi",
              "Roc", "Ros", "Debt Related", "Same store sales", "Same Store Sales", "Book Value", "Working Capital",
              "Cost Reduction", "Balance Sheet Related", "Sales Contracts", "IPO of Subsidiary", "FDA Approval", "Fda Approval"}
EXT_LABELS = {"Customer Satisfaction"}
PLACEHOLDER_LABELS = {"", "Other", "Individual", "Vague", "Non-Financial", "Operational", "Discretionary", "Business Unit"}

COMPILED = []
for i, r in enumerate(R, 1):
    rid = f"R{i:03d}_{r['topic']}"
    COMPILED.append((rid, r["kind"], r["topic"], r["pillar"], r["confidence"], re.compile(r["pattern"], re.I)))


def scan(text):
    """Apply rules in order; each match consumes its span. Returns list of (rule_id, kind, topic, pillar, conf, matched)."""
    hits, t = [], f" {text} "
    for rid, kind, topic, pillar, conf, pat in COMPILED:
        found = []
        def _sub(m):
            found.append(m.group(0).strip())
            return " " + "_" * max(1, len(m.group(0)) - 2) + " "
        t = pat.sub(_sub, t)
        for f in found:
            hits.append((rid, kind, topic, pillar, conf, f))
            if kind == "MASKN":   # masked phrase that is itself informative non-ESG content
                hits.append((rid, "NONESG", topic, "", conf, f))
    return hits


def decide(hits):
    kinds = {h[1] for h in hits}
    esg = [h for h in hits if h[1] == "ESG"]
    if esg:
        strict = 1
    elif "AMB" in kinds or "NONSPEC" in kinds:
        strict = None
    elif kinds & {"EXT", "EXT_AMB", "ADJ", "NONESG"}:
        strict = 0
    else:
        strict = None
    if strict == 1 or "EXT" in kinds:
        ext = 1
    elif strict is None or "EXT_AMB" in kinds:
        ext = None
    else:
        ext = 0
    # pillars (Strict only)
    # 中文：维度判断——有该维度的具体证据记 1；有通用 ESG 词（ESG/CSR/可持续）或该维度的模糊词时记“未知”；否则记 0。
    pill = {}
    spec = {h[3] for h in esg if h[3] in ("E", "S", "G")}
    amb_pillars = {h[3] for h in hits if h[1] == "AMB" and h[3] in ("E", "S", "G")}   # v1.1: e.g. 'safety and governance' -> G unknown
    gen_esg = any(h[2] == "GEN_esg" for h in esg)
    gen_sus = any(h[2] == "GEN_sustainability" for h in esg)
    unresolved_pillars = gen_esg or (gen_sus and not spec)
    for p in ("E", "S", "G"):
        if strict == 1:
            pill[p] = 1 if p in spec else (None if (unresolved_pillars or p in amb_pillars) else 0)
        else:
            pill[p] = 0 if strict == 0 else None
    return strict, ext, pill


def extended_only(strict, ext):
    """1 = Extended but not Strict; 0 = not Extended, or Strict; Unknown when it cannot be decided (v1.1 fix:
    Strict Unknown + Extended 1 used to be coded 1)."""
    if ext == 0 or strict == 1:
        return 0
    if ext == 1 and strict == 0:
        return 1
    return None


def classify_unit(metric, other, metric_type=""):
    """Return dict with primary label (may use structured context) and text-only label."""
    hits = scan(other) if other else []
    label_note = ""
    if metric in FIN_LABELS:
        hits.append(("L01_fin_label", "NONESG", "N_metric_label", "", "high", metric)); label_note = "financial metric label"
    elif metric in EXT_LABELS:
        hits.append(("L02_custsat_label", "EXT", "X_customer", "", "high", metric)); label_note = "customer-satisfaction metric label"
    elif metric in ISS_2018_ESG_METRIC_LABELS:
        label_note = "2018-taxonomy ESG label ignored (diagnostic only)"
    if metric in FIN_LABELS and other and len(other.split()) <= 2 and not any(h[1] in ("ESG", "EXT", "AMB", "EXT_AMB") for h in hits):
        # e.g. metric='Cashflow', metricOther='Discretionary' / 'Operations': qualifier of the financial label
        hits = [h for h in hits if h[1] != "NONSPEC"]
    strict, ext, pill = decide(hits)
    method, ctx = "deterministic_rule", ""
    t_strict, t_ext, t_pill = strict, ext, dict(pill)
    if not other and (metric in PLACEHOLDER_LABELS or metric in ISS_2018_ESG_METRIC_LABELS):
        if metric in ISS_2018_ESG_METRIC_LABELS:
            ctx, method = "iss_esg_label_only", "unresolved"
        elif metric_type in FIN_METRICTYPES:
            ctx, method = "fin_metrictype", "structured_context"
            strict, ext, pill = 0, 0, {"E": 0, "S": 0, "G": 0}
            hits.append(("C01_fin_metrictype", "NONESG", "N_structured_context", "", "medium", metric_type))
        else:
            ctx, method = "no_text", "unresolved"
    if strict is None and method == "deterministic_rule":
        method = "unresolved"
    kinds = [h[1] for h in hits]
    conf = ("high" if all(h[4] == "high" for h in hits if h[1] in ("ESG", "EXT", "NONESG")) else "medium") if strict is not None else "low"
    if method == "structured_context":
        conf = "medium"
    flags = []
    if strict == 1 and metric in FIN_LABELS:
        flags.append("esg_term_under_financial_label")
    if strict == 1 and "NONESG" in kinds:
        flags.append("mixed_esg_and_financial_text")
    if strict == 1 and "NONSPEC" in kinds:
        flags.append("esg_within_composite_description")
    adj = sorted({h[2] for h in hits if h[1] == "ADJ"})
    reason = "; ".join(f"{h[0]}[{h[1]}]:'{h[5]}'" for h in hits if h[1] not in ("MASK", "MASKN", "FILLER"))
    masked = "; ".join(f"{h[0]}:'{h[5]}'" for h in hits if h[1] in ("MASK", "MASKN"))
    topics = sorted({h[2] for h in hits if h[1] in ("ESG", "EXT")})
    return dict(esg_strict=strict, esg_extended=ext, esg_extended_only=extended_only(strict, ext),
                esg_e=pill["E"], esg_s=pill["S"], esg_g=pill["G"],
                esg_general=int(any(h[2].startswith("GEN") for h in hits if h[1] == "ESG")),
                esg_strict_textonly=t_strict, esg_extended_textonly=t_ext,
                classification_method=method, classification_confidence=conf, context_used=ctx,
                esg_topics="|".join(topics), adjacent_flags="|".join(adj), review_flags="|".join(flags),
                classification_reason=(reason or ("no informative text" if not other else "no rule matched")) +
                                      (f" || masked: {masked}" if masked else "") + (f" || {label_note}" if label_note else ""),
                rule_ids="|".join(sorted({h[0] for h in hits if h[1] not in ("FILLER",)})))
