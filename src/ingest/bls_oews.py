"""
Download BLS Occupational Employment and Wage Statistics (OEWS) national data.
No API key required. Downloads national Excel files directly from bls.gov.
Coverage: 2013–2023.

Each national file contains:
  - All-industry aggregate occupation wages (NAICS blank/"000000")
  - Industry-specific all-occupation wages (OCC_CODE "00-0000" + specific NAICS)
"""
import io
import zipfile
import requests
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw/bls")
YEARS = list(range(2013, 2024))

# BLS changes the URL pattern occasionally; try each in order
URL_PATTERNS = [
    "https://www.bls.gov/oes/special.requests/oesnat{yy}.zip",
    "https://www.bls.gov/oes/special.requests/oesm{yy}nat.zip",
]

# Normalize column names across different BLS file vintages
COL_MAP = {
    "OCC_CODE": "occ_code",
    "OCC_TITLE": "occ_title",
    "GROUP": "occ_group",
    "OCC_GROUP": "occ_group",
    "NAICS": "naics",
    "NAICS_TITLE": "naics_title",
    "I_GROUP": "i_group",
    "OWN_CODE": "own_code",
    "TOT_EMP": "tot_emp",
    "H_MEAN": "h_mean",
    "A_MEAN": "a_mean",
    "H_PCT10": "h_pct10",
    "H_PCT25": "h_pct25",
    "H_MEDIAN": "h_median",
    "H_PCT75": "h_pct75",
    "H_PCT90": "h_pct90",
    "A_PCT10": "a_pct10",
    "A_PCT25": "a_pct25",
    "A_MEDIAN": "a_median",
    "A_PCT75": "a_pct75",
    "A_PCT90": "a_pct90",
}

KEEP_COLS = [
    "occ_code", "occ_title", "occ_group", "naics", "naics_title",
    "tot_emp", "a_mean", "a_median", "a_pct10", "a_pct25", "a_pct75", "a_pct90",
    "year",
]

NUMERIC_COLS = ["tot_emp", "a_mean", "a_median", "a_pct10", "a_pct25", "a_pct75", "a_pct90"]


def _download_zip(year: int) -> bytes:
    yy = str(year)[2:]
    for pattern in URL_PATTERNS:
        url = pattern.format(yy=yy)
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 200 and len(resp.content) > 1000:
                print(f"    Downloaded from {url}")
                return resp.content
        except Exception:
            continue
    raise RuntimeError(
        f"Could not download BLS OEWS {year}. "
        f"Try manually downloading from https://www.bls.gov/oes/tables.htm"
    )


def pull_year(year: int) -> pd.DataFrame:
    raw = _download_zip(year)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        excel_names = [n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xls"))]
        if not excel_names:
            raise ValueError(f"No Excel file found inside BLS zip for {year}")
        with zf.open(excel_names[0]) as f:
            df = pd.read_excel(f, dtype=str)

    df.columns = [c.strip().upper() for c in df.columns]
    df = df.rename(columns={k: v for k, v in COL_MAP.items() if k in df.columns})
    df["year"] = year

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = [c for c in KEEP_COLS if c in df.columns]
    return df[keep]


def pull_all() -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    frames = []

    for year in YEARS:
        print(f"  BLS OEWS {year}...")
        try:
            df = pull_year(year)
            frames.append(df)
            print(f"    {len(df):,} rows")
        except Exception as exc:
            print(f"    {year} skipped: {exc}")

    combined = pd.concat(frames, ignore_index=True)
    out = RAW_DIR / "oews_national.parquet"
    combined.to_parquet(out, index=False)
    print(f"  Saved {len(combined):,} rows → {out}")
    return combined
