"""Download Dropbox files (dl=1 direct links) and verify they are real files, not HTML pages."""
import sys, requests

FILES = {
    "ESG_Metrics_Paper.pdf": "https://www.dropbox.com/scl/fi/ex9zwe281piblwppvzrfs/ESG-Metrics-in-Executive-Compensation-A-Multitasking-Approach.pdf?rlkey=7gortbjz4xge8lh4nw7sdohnw&st=e9lvve7c&dl=1",
    "Research_Task.docx": "https://www.dropbox.com/scl/fi/e7uop39luuiiwag273zx1/Research-Data-Engineering-Task.docx?rlkey=b0emi34h3kwr1l0cr7nsxepxi&st=uuzsoyr2&dl=1",
}
MAGIC = {".pdf": b"%PDF", ".docx": b"PK\x03\x04"}

for name, url in FILES.items():
    r = requests.get(url, timeout=120, allow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    head = r.content[:8]
    ext = name[name.rfind("."):]
    if not head.startswith(MAGIC[ext]):
        sys.exit(f"{name}: got {r.headers.get('Content-Type')} (starts {head!r}), not a real {ext} file")
    with open(name, "wb") as f:
        f.write(r.content)
    print(f"{name}: {len(r.content):,} bytes, Content-Type={r.headers.get('Content-Type')}, magic OK")
