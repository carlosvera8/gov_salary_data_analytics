"""
Clean raw Census ACS data and produce inflation-adjusted parquet files for the dashboard.
Output: data/processed/census_clean.parquet
"""
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

# BLS CPI-U All Items, annual averages, not seasonally adjusted (Series CUUR0000SA0)
# Used to convert nominal dollars to constant 2023 dollars
CPI_U = {
    2010: 218.056, 2011: 224.939, 2012: 229.594, 2013: 232.957,
    2014: 236.736, 2015: 237.017, 2016: 240.007, 2017: 245.120,
    2018: 251.107, 2019: 255.657, 2020: 258.811, 2021: 270.970,
    2022: 292.655, 2023: 304.702,
}
BASE_YEAR = 2023
MONEY_PREFIXES = ("median_", "mean_", "occ_earn_", "ind_earn_")


def _cpi_factor(year: int) -> float:
    return CPI_U[BASE_YEAR] / CPI_U.get(year, CPI_U[BASE_YEAR])


def clean_census() -> pd.DataFrame:
    path = RAW_DIR / "census/acs_income_demographics.parquet"
    df = pd.read_parquet(path)

    # Inflation multiplier per row
    df["cpi_factor"] = df["year"].map(_cpi_factor)

    # Add _real variants for every money column
    money_cols = [c for c in df.columns if any(c.startswith(p) for p in MONEY_PREFIXES)]
    for col in money_cols:
        df[f"{col}_real"] = (df[col] * df["cpi_factor"]).round(0)

    # Human-readable metro name: take everything before the first comma
    if "NAME" in df.columns:
        df["metro_name"] = df["NAME"].str.split(",").str[0].str.strip()
    else:
        df["metro_name"] = df.get("geo_id", pd.Series("", index=df.index))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "census_clean.parquet"
    df.to_parquet(out, index=False)
    print(f"  Census: {len(df):,} rows -> {out}")
    return df
