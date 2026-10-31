"""Shared paths/constants. Raw ISS files are read-only; set ISS_RAW_DIR to their folder."""
import os, pathlib
PROJ = pathlib.Path(__file__).resolve().parents[1]
RAW = pathlib.Path(os.environ.get("ISS_RAW_DIR", "/tmp/incentive_lab/extracted/01. Incentive Lab"))
PAPER_PDF = pathlib.Path(os.environ.get("PAPER_PDF", PROJ.parent / "ESG_Metrics_Paper.pdf"))
DICT = PROJ / "dictionaries"; INTER = PROJ / "data" / "intermediate"; FINAL = PROJ / "data" / "final"
VALID = PROJ / "validation"; REPORTS = PROJ / "reports"; LOGS = PROJ / "logs"
GOAL_FILES = {  # source tag -> (file, row id, period id column)
    "ABS": ("02. Absolute Performance Goals Data.dta", "absId", "periodID"),
    "REL": ("16. Relative Performance Goals Data.dta", "relId", "periodId"),
    "ACC": ("03. Accelerated Performance Goals Data.dta", "accId", "periodId"),
}
# ISS taxonomy fields used ONLY for ex-post diagnostics, never for classification.
ISS_ESG_METRICTYPES = {"Social", "Environment", "CSR"}
# `metric` labels that first appear with the 2018 ISS re-taxonomy (verified in 02_build_kpi_text log).
ISS_2018_ESG_METRIC_LABELS = {
    "Staff Health And Safety", "Diversity", "Staff Relations, Engagement And Training", "Csr",
    "Climate Change And Energy Use", "Environmental Protection", "Customer And Product Responsibility",
    "Resource Use", "Society And Human Rights", "Labor Conditions In Supply Chain",
    "Staff Relations, Engagement And"}  # truncated variant in the relative-goals file
PAPER_CITATION = ("Agarwal, V., Gómez, J.-P., Hosseini, K., Jha, M. (2025). ESG Metrics in Executive "
                  "Compensation: A Multitasking Approach. CFR Working Paper No. 25-10, Appendix A.3. "
                  "List originally from Gantchev, Giannetti & Hober (2024), 'Beyond ESG: Executive Pay "
                  "Metrics and Shareholder Support', FEB-RN Research Paper No. 26/2024 (1,034 terms; "
                  "81 removed by AGHJ using a post-2018 ISS false-positive ratio > 50%).")
