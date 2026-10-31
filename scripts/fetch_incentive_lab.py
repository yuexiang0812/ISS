"""Download the Incentive Lab Dropbox archive, extract it, and summarize its contents."""
import sys, zipfile, pathlib
import requests
import pandas as pd

URL = ("https://www.dropbox.com/scl/fi/irikglhvb0mk6k7p33fn6/01.-Incentive-Lab.zip"
       "?rlkey=wmttfs7k1rccir580rvwruwlz&st=9ykudp6t&dl=1")

def download(dest: pathlib.Path) -> pathlib.Path:
    zpath = dest / "incentive_lab.zip"
    if not zpath.exists():
        with requests.get(URL, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    print(f"Downloaded: {zpath} ({zpath.stat().st_size/1e6:.1f} MB)")
    return zpath

def extract(zpath: pathlib.Path, dest: pathlib.Path) -> pathlib.Path:
    out = dest / "extracted"
    with zipfile.ZipFile(zpath) as z:
        print("\nArchive contents (excluding macOS metadata):")
        for i in z.infolist():
            if "__MACOSX" in i.filename or i.filename.endswith(".DS_Store") or i.is_dir():
                continue
            print(f"  {i.filename:80s} {i.file_size/1e6:10.2f} MB")
        z.extractall(out, members=[m for m in z.infolist() if "__MACOSX" not in m.filename])
    return out

def read_table(p: pathlib.Path):
    s = p.suffix.lower()
    if s == ".csv":  return pd.read_csv(p, low_memory=False, encoding_errors="replace")
    if s in (".txt", ".tsv"): return pd.read_csv(p, sep=None, engine="python", encoding_errors="replace")
    if s in (".xlsx", ".xls"): return pd.read_excel(p)
    if s == ".dta": return pd.read_stata(p)
    if s == ".sas7bdat": return pd.read_sas(p)
    if s == ".parquet": return pd.read_parquet(p)
    return None

def summarize(root: pathlib.Path):
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or "__MACOSX" in rel.parts or p.name.startswith("."):
            continue  # skip macOS metadata junk
        print("\n" + "=" * 100 + f"\nFILE: {p.relative_to(root)}  ({p.stat().st_size/1e6:.2f} MB)")
        try:
            df = read_table(p)
        except Exception as e:
            print(f"  could not read: {e}"); continue
        if df is None:
            print("  (non-tabular file, skipped)"); continue
        print(f"  shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
        info = pd.DataFrame({"dtype": df.dtypes.astype(str),
                             "non_null": df.notna().sum(),
                             "null_pct": (df.isna().mean()*100).round(1),
                             "n_unique": df.nunique()})
        with pd.option_context("display.max_rows", 500, "display.width", 200, "display.max_columns", 50):
            print(info.to_string())
            print("\n  head(3):"); print(df.head(3).to_string())

if __name__ == "__main__":
    dest = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/incentive_lab").resolve()
    dest.mkdir(parents=True, exist_ok=True)
    summarize(extract(download(dest), dest))
