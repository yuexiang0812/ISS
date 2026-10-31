"""Master script: reproduces the full pipeline from the raw ISS files.

Usage:  ISS_RAW_DIR="/path/to/01. Incentive Lab" PAPER_PDF=/path/to/ESG_Metrics_Paper.pdf python master_run.py [first_step]
Each step is also runnable on its own (python NN_name.py). Any failure stops the run (no error is suppressed).
Requirements: python>=3.10, pandas, numpy, pyarrow; poppler-utils (pdftotext) for step 02; node + docx and pandoc for step 17.
"""
import subprocess, sys, time, pathlib

STEPS = ["01_data_inventory.py", "02_extract_paper_dictionary.py", "03_goal_extraction.py", "04_text_classification.py",
         "05_dictionary_deliverables.py", "06_dataset_A_text_dictionary.py", "07_dataset_B_kpi.py", "08_dataset_C_grant.py",
         "09_dataset_D_executive.py", "10_dataset_E_ceo.py", "11_dataset_F_G_firm.py", "12_paper_vs_revised_comparison.py",
         "13_validation.py", "14_annual_trends.py", "15_variable_dictionary.py",
         "16_quality_audit.py", "17_build_reports.py", "18_build_audit_archive.py"]
here = pathlib.Path(__file__).parent
start = sys.argv[1] if len(sys.argv) > 1 else STEPS[0][:2]
for s in STEPS:
    if s[:2] < start:
        continue
    t = time.time(); print(f"=== {s}", flush=True)
    r = subprocess.run([sys.executable, s], cwd=here)
    if r.returncode != 0:
        sys.exit(f"step {s} failed (exit {r.returncode}); see Logs/")
    print(f"=== {s} done in {time.time() - t:.0f}s", flush=True)
print("pipeline complete")
