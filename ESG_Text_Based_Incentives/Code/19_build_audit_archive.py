"""Step 19 — Self-contained audit archive (local only; contains ISS-licensed data).

Creates  ../Audit_Archive/ESG_Audit_Archive_<version>_<timestamp>.zip  and a matching  *_MANIFEST.csv  with:
  project/   the whole ESG_Text_Based_Incentives tree (code, dictionaries, logs, validation, annual, documentation +
             Word reports, intermediate and final datasets)
  inputs/    paper PDF, task docx, initial download/summary scripts and the initial data summary
  session/   raw session transcript (JSONL), git log, git bundle of the full repository history
  environment/ python / package / tool versions
  ARCHIVE_README.md
Every file is listed in MANIFEST.csv with size and SHA-256 (verify with: sha256sum). The raw ISS zip is NOT copied;
its source URL and SHA-256 are recorded so the exact input can be verified.
"""
import hashlib, os, glob, subprocess, zipfile, datetime as dt, platform, csv, io, pathlib
from config import PROJ, CLASSIFIER_VERSION, get_logger

log = get_logger("19_build_audit_archive")
REPO = PROJ.parent
OUTDIR = REPO / "Audit_Archive"; OUTDIR.mkdir(exist_ok=True)
stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
name = f"ESG_Audit_Archive_{CLASSIFIER_VERSION}_{stamp}"
RAW_ZIP = pathlib.Path(os.environ.get("ISS_RAW_ZIP", "/tmp/incentive_lab/incentive_lab.zip"))
RAW_URL = "Dropbox shared link provided by the user (see inputs/scripts/fetch_incentive_lab.py)"


def sha(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(buf), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO).stdout


files = []  # (source path, archive path)
for p in sorted(PROJ.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("_spec_"):
        files.append((p, "project/ESG_Text_Based_Incentives/" + str(p.relative_to(PROJ))))
for rel in ["ESG_Metrics_Paper.pdf", "Research_Task.docx", "scripts/download_files.py", "scripts/fetch_incentive_lab.py",
            "reports/incentive_lab_summary.txt", ".gitignore"]:
    if (REPO / rel).exists():
        files.append((REPO / rel, "inputs/" + rel))
for t in glob.glob("/root/.claude/projects/*ISS*/*.jsonl"):
    files.append((pathlib.Path(t), "session/" + os.path.basename(t)))

tmp = OUTDIR / f"_{name}_tmp"; tmp.mkdir(exist_ok=True)
(tmp / "git_log.txt").write_text(run("git log --stat --date=iso"))
subprocess.run(["git", "bundle", "create", str(tmp / "repository.bundle"), "--all"], cwd=REPO, capture_output=True)
env = (f"python {platform.python_version()} on {platform.platform()}\n" + run("node --version") + run("pandoc --version | head -1") +
       run("pdftotext -v 2>&1 | head -1") + "\n--- pip freeze ---\n" + run("python -m pip freeze 2>/dev/null"))
(tmp / "environment.txt").write_text(env)
raw_hash = sha(RAW_ZIP) if RAW_ZIP.exists() else "raw zip not available in this environment"
readme = f"""# ESG Text-Based Incentives — audit archive ({CLASSIFIER_VERSION}, {stamp})

CONFIDENTIAL: contains ISS Incentive Lab licensed data and private download links. Do not redistribute.

## Contents
- project/ESG_Text_Based_Incentives/ — complete project: Code/ (pipeline 01-18, master_run.py), Dictionaries/ (deliverables a-c),
  Data/Intermediate (parquet + audit tables), Data/Final (.dta datasets), Validation/, Annual_Analysis/, Logs/,
  Documentation/ (methodology report, variable dictionary, quality audit results, Reports/*.docx incl. conversation archive)
- inputs/ — paper PDF (MD5 e50f74f68d94ee35b39cbd78847a470d), task brief docx, initial download & summary scripts
- session/ — raw transcript of the working session (JSONL: every message, tool call and tool output), git_log.txt,
  repository.bundle (full git history: `git clone repository.bundle repo`)
- environment/environment.txt — software versions
- MANIFEST.csv — size and SHA-256 of every file in this archive

## Raw input (not included)
ISS Incentive Lab zip: {RAW_URL}
SHA-256 of the zip used: {raw_hash}

## Reproduce
cd project/ESG_Text_Based_Incentives/Code && ISS_RAW_DIR="<unzipped>/01. Incentive Lab" PAPER_PDF=../../../inputs/ESG_Metrics_Paper.pdf python master_run.py
"""
(tmp / "ARCHIVE_README.md").write_text(readme)
files += [(tmp / "git_log.txt", "session/git_log.txt"), (tmp / "repository.bundle", "session/repository.bundle"),
          (tmp / "environment.txt", "environment/environment.txt"), (tmp / "ARCHIVE_README.md", "ARCHIVE_README.md")]

man = io.StringIO(); w = csv.writer(man); w.writerow(["archive_path", "bytes", "sha256"])
rows = [(arc, src.stat().st_size, sha(src)) for src, arc in files]
for r in rows:
    w.writerow(r)
zpath = OUTDIR / f"{name}.zip"
with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
    for src, arc in files:
        z.write(src, arc)
    z.writestr("MANIFEST.csv", man.getvalue())
(OUTDIR / f"{name}_MANIFEST.csv").write_text(man.getvalue())
for p in tmp.iterdir():
    p.unlink()
tmp.rmdir()
with zipfile.ZipFile(zpath) as z:
    bad = z.testzip()
log.info(f"archive {zpath.name}: {len(files)+1} files, {zpath.stat().st_size/1e6:.0f} MB zipped, "
         f"{sum(r[1] for r in rows)/1e6:.0f} MB raw; zip integrity test: {'OK' if bad is None else 'FAILED at ' + bad}")
log.info(f"archive sha256: {sha(zpath)}")
assert bad is None
