"""Shared paths, constants and helpers.

Raw ISS files are read-only. Set ISS_RAW_DIR to the folder holding the 18 .dta files.
"""
import os, pathlib, logging, sys
import numpy as np, pandas as pd

PROJ = pathlib.Path(__file__).resolve().parents[1]
RAW = pathlib.Path(os.environ.get("ISS_RAW_DIR", "/tmp/incentive_lab/extracted/01. Incentive Lab"))
PAPER_PDF = pathlib.Path(os.environ.get("PAPER_PDF", PROJ.parent / "ESG_Metrics_Paper.pdf"))
CODE = PROJ / "Code"; DICT = PROJ / "Dictionaries"; INTER = PROJ / "Data" / "Intermediate"
FINAL = PROJ / "Data" / "Final"; VALID = PROJ / "Validation"; LOGS = PROJ / "Logs"
DOCS = PROJ / "Documentation"; ANNUAL = PROJ / "Annual_Analysis"
for d in (DICT, INTER, FINAL, VALID, LOGS, DOCS, ANNUAL):
    d.mkdir(parents=True, exist_ok=True)

CLASSIFIER_VERSION = "v1.0"          # bump on any rule change; see Dictionaries/c_change_log.csv
YEARS = range(1998, 2022)

FILES = {
    "company": "05. Company Data by Fiscal Year.dta",
    "participant": "12. Participant Data by Fiscal Year.dta",
    "grant": "08. Grants of Plan-Based Awards Table.dta",
    "abs": "02. Absolute Performance Goals Data.dta",
    "rel": "16. Relative Performance Goals Data.dta",
    "acc": "03. Accelerated Performance Goals Data.dta",
    "sumcomp": "18. Summary Compensation Table.dta",
}
GOAL_FILES = {  # goal_source -> (file key, objective id column, period id column)
    "ABS": ("abs", "absId", "periodID"),
    "REL": ("rel", "relId", "periodId"),
    "ACC": ("acc", "accId", "periodId"),
}
PERF_TYPES = {"Abs", "Rel", "AbsRel"}     # performancetype values = performance-vesting award

# ISS taxonomy, used ONLY for ex-post diagnostics (never as ESG evidence)
ISS_ESG_METRICTYPES = {"Social", "Environment", "CSR"}
ISS_2018_ESG_METRIC_LABELS = {
    "Staff Health And Safety", "Diversity", "Staff Relations, Engagement And Training", "Csr",
    "Climate Change And Energy Use", "Environmental Protection", "Customer And Product Responsibility",
    "Resource Use", "Society And Human Rights", "Labor Conditions In Supply Chain",
    "Staff Relations, Engagement And"}  # last = truncated variant in the relative-goals file
# Financial metricType categories that exist consistently in all years
# ("Market-related" is the post-2018 name of "Stock Price", ISS User Guide p.12).
# Used ONLY as structured context when BOTH metric and metricOther are blank.
FIN_METRICTYPES = {"Accounting", "Stock Price", "Market-related", "Earnings/Profit-related", "Revenue-related",
                   "Cash Flow", "Financial/Investment return ratios", "Financial/Investment return rati",
                   "Liquidity/Solvency-related", "Balance Sheet-related", "Economic Value", "Activity-related"}

PAPER_CITATION = ("Agarwal, V., Gómez, J.-P., Hosseini, K., Jha, M. (2025). ESG Metrics in Executive "
                  "Compensation: A Multitasking Approach. CFR Working Paper No. 25-10, Appendix A.3. "
                  "List originally from Gantchev, Giannetti & Hober (2024), 'Beyond ESG: Executive Pay "
                  "Metrics and Shareholder Support', FEB-RN Research Paper No. 26/2024 (1,034 terms; "
                  "81 removed by AGHJ using a post-2018 ISS false-positive ratio > 50%).")


def read_raw(key, columns=None):
    return pd.read_stata(RAW / FILES[key], columns=columns)


def clean_missing_codes(s: pd.Series) -> pd.Series:
    """ISS codes missing numerics as -9999.xx (User Guide p.3); some fields use -99999.
    Returns NaN for any value <= -9999."""
    s = pd.to_numeric(s, errors="coerce")
    return s.where(~(s <= -9999))


def clean_missing_dates(s: pd.Series) -> pd.Series:
    """Missing dates are coded 01/01/9999 (read as year 9998/9999)."""
    s = pd.to_datetime(s, errors="coerce")
    return s.where(s.dt.year < 9000)


def get_logger(name):
    lg = logging.getLogger(name); lg.setLevel(logging.INFO); lg.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for h in (logging.FileHandler(LOGS / f"{name}.log", mode="w", encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt); lg.addHandler(h)
    return lg


def check_unique(df, keys, name, log):
    d = int(df.duplicated(keys).sum())
    log.info(f"[key check] {name}: {len(df):,} rows; key {keys} duplicates = {d}")
    assert d == 0, f"{name}: duplicate keys {keys}"


def check_share(df, cols, log, name):
    for c in cols:
        s = df[c].dropna()
        bad = int(((s < 0) | (s > 1)).sum())
        log.info(f"[share check] {name}.{c}: n={len(s):,} out-of-[0,1]={bad}")
        assert bad == 0, f"{name}.{c} outside [0,1]"
