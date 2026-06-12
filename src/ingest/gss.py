"""
Load GSS (General Social Survey) data from a downloaded CSV.

Download instructions (5 min, free account required):
  1. Go to gssdataexplorer.norc.org and create a free account
  2. Click "Extract Data" -> "Select Variables"
  3. Search for and add: YEAR, HAPPY, REALINC, FAMSIZE, SEX, RACE, CHILDS
  4. Select all years, download as CSV
  5. Save the file anywhere inside data/raw/gss/
"""
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw/gss")

HAPPY_MAP   = {1: "Very Happy", 2: "Pretty Happy", 3: "Not Too Happy"}
HAPPY_SCORE = {1: 3, 2: 2, 3: 1}  # higher = happier
RACE_MAP    = {1: "White", 2: "Black", 3: "Other"}
SEX_MAP     = {1: "Male", 2: "Female"}
QUINTILE_ORDER = ["Bottom 20%", "Lower-Middle", "Middle", "Upper-Middle", "Top 20%"]


def load_gss() -> pd.DataFrame:
    files = list(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No CSV found in {RAW_DIR}/. "
            "See download instructions at the top of src/ingest/gss.py."
        )
    path = sorted(files)[-1]
    df = pd.read_csv(path, low_memory=False)
    df.columns = df.columns.str.lower().str.strip()
    # Some GSS export tools include a label row as row 2 — detect and skip
    if "year" in df.columns:
        if not pd.to_numeric(df["year"].iloc[0], errors="coerce") > 0:
            df = df.iloc[1:].reset_index(drop=True)
    return df
