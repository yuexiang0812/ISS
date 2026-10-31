"""(a) Extract the 953-keyword list verbatim from Appendix A.3 of Agarwal et al. (2025).

Uses `pdftotext -layout` (poppler). Layout mode is required: raw mode reorders words on fully
justified lines (it produced the spurious token 'CO2 coal-exit' and lost 'CO2 reduction').
No term is added, removed or corrected; known print artifacts are only annotated.
"""
import re, subprocess, hashlib, collections
import pandas as pd
from config import PAPER_PDF, DICT, PAPER_CITATION

txt = subprocess.run(["pdftotext", "-layout", str(PAPER_PDF), "-"], capture_output=True, text=True, check=True).stdout
start_tag = "to classify compensation contracts as related to ESG:"
s = txt.index(start_tag) + len(start_tag); e = txt.index("A.4", s)
block = txt[s:e]

# Walk lines, tracking printed page numbers (a line holding only a number ends a page).
page, rows, buf = 59, [], ""
pending = []  # (term_text, page)
for line in block.split("\n"):
    l = line.strip()
    if not l: continue
    if re.fullmatch(r"\d+", l):
        page = int(l) + 1; continue
    if not buf: buf_page = page  # page where the current (unfinished) term starts
    if buf.endswith("-"): buf += l
    else: buf = (buf + " " + l) if buf else l
    *done, buf = buf.split(",")
    for d in done:
        pending.append((d, buf_page)); buf_page = page
pending.append((buf.rstrip(". "), buf_page))
terms = [(re.sub(r"\s+", " ", t).strip(), p) for t, p in pending if t.strip()]

notes = {
    "women‚Äôs": "Printed as-is: UTF-8 mojibake of \"women's\" in the source list (also listed correctly as 'women’s sponsorship').",
    "multiculural": "Printed as-is (likely typo of 'multicultural'); not corrected.",
}
df = pd.DataFrame(terms, columns=["keyword", "source_page"])
df.insert(0, "kw_id", [f"P{i:04d}" for i in range(1, len(df) + 1)])
df["n_tokens"] = df.keyword.str.split().str.len()
df["is_acronym_like"] = df.keyword.str.fullmatch(r"[A-Z0-9][A-Z0-9&\-]*s?").fillna(False)
df["extraction_note"] = df.keyword.map(notes).fillna("")
df["source"] = PAPER_CITATION
assert len(df) == 953, len(df)
assert df.keyword.is_unique, [k for k, v in collections.Counter(df.keyword).items() if v > 1]
df.to_csv(DICT / "a_paper_dictionary_AGHJ2025_953.csv", index=False, encoding="utf-8")

# A.4: the only removed (81) terms disclosed by the paper, with its printed false-positive examples.
a4 = [("complaint", "Customer Complaint"), ("complaint", "On-time complaint quality reporting"),
      ("complaint", "Complaint Tracking Module Volume per 1,000 members per month"),
      ("complaint", "Complaint Management"), ("complaint", "Complaint Timeliness Execution"),
      ("cyber", "Cyber Mindset results for Finance and Corporate Development departments"),
      ("cyber", "Cyber Mindset results"), ("cyber", "Cyber Mindset results for US Markets"),
      ("cyber", "Technology and Cyber Risk Management"),
      ("trust", "Execution of The Trust’s Capital Plan"), ("trust", "Trust and Brokerage as Measured Against Their Combined Goals"),
      ("trust", "Composition of Trust’s Portfolio"), ("trust", "Merck Trust & Value Customer Survey"),
      ("trust", "MS Leader in Customer Trust and Value Survey"),
      ("trust", "Wells Fargo Institutional Retirement Trust Integration Scorecard ..."),
      ("trust", "Enhance customer trust by achieving targeted product safety ..."), ("trust", "Performance of Commerce Trust")]
pd.DataFrame(a4, columns=["removed_keyword", "example_metricother_printed"]).assign(
    esg_comp_metric_per_paper=0, source="Agarwal et al. (2025), Appendix A.4, Tables A.1-A.3 (p. 64)",
    note="Only 3 of the 81 removed terms are disclosed; the other 78 are unknown and NOT reconstructed."
).to_csv(DICT / "a_paper_removed_keywords_examples_A4.csv", index=False)
print(f"extracted {len(df)} unique keywords from pages {df.source_page.min()}-{df.source_page.max()}; "
      f"pdf md5={hashlib.md5(PAPER_PDF.read_bytes()).hexdigest()}")
print(df.source_page.value_counts().sort_index().to_string())
