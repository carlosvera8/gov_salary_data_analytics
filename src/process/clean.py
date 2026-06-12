"""
Clean raw data and produce inflation-adjusted parquet files for the dashboard.
Outputs:
  data/processed/census_clean.parquet
  data/processed/gss_clean.parquet  (only if GSS data has been downloaded)
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
CPI_1986 = 109.6  # BLS CPI-U 1986 annual average — GSS realinc base year
MONEY_PREFIXES = ("median_", "mean_", "occ_earn_", "ind_earn_")


def _cpi_factor(year: int) -> float:
    return CPI_U[BASE_YEAR] / CPI_U.get(year, CPI_U[BASE_YEAR])


def clean_census() -> pd.DataFrame:
    path = RAW_DIR / "census/acs_income_demographics.parquet"
    df = pd.read_parquet(path)

    df["cpi_factor"] = df["year"].map(_cpi_factor)

    money_cols = [c for c in df.columns if any(c.startswith(p) for p in MONEY_PREFIXES)]
    for col in money_cols:
        df[f"{col}_real"] = (df[col] * df["cpi_factor"]).round(0)

    if "NAME" in df.columns:
        df["metro_name"] = df["NAME"].str.split(",").str[0].str.strip()
    else:
        df["metro_name"] = df.get("geo_id", pd.Series("", index=df.index))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "census_clean.parquet"
    df.to_parquet(out, index=False)
    print(f"  Census: {len(df):,} rows -> {out}")
    return df


def clean_gss() -> pd.DataFrame:
    from src.ingest.gss import load_gss, HAPPY_MAP, HAPPY_SCORE, RACE_MAP, SEX_MAP, QUINTILE_ORDER

    df = load_gss()

    for col in ["year", "happy", "realinc", "famsize", "sex", "race", "childs"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep only valid happiness responses (removes iap/dk/na codes)
    df = df[df["happy"].isin([1, 2, 3])].copy()

    df["happy_label"] = df["happy"].map(HAPPY_MAP)
    df["happy_score"] = df["happy"].map(HAPPY_SCORE)
    df["is_very_happy"] = (df["happy"] == 1).astype(float)

    if "race" in df.columns:
        df["race_label"] = df["race"].map(RACE_MAP).fillna("Other")
    if "sex" in df.columns:
        df["sex_label"] = df["sex"].map(SEX_MAP)

    # Convert GSS realinc (constant 1986$) to 2023 dollars
    if "realinc" in df.columns:
        inc_mask = df["realinc"].notna() & (df["realinc"] > 0)
        df["realinc_2023"] = pd.NA
        df.loc[inc_mask, "realinc_2023"] = (
            df.loc[inc_mask, "realinc"] * CPI_U[BASE_YEAR] / CPI_1986
        ).round(0)
        # Quintiles computed across all valid responses
        valid = df["realinc_2023"].notna()
        df["income_quintile"] = pd.NA
        df.loc[valid, "income_quintile"] = pd.qcut(
            df.loc[valid, "realinc_2023"], q=5, labels=QUINTILE_ORDER
        )

    # Household size: group 7+ together
    if "famsize" in df.columns:
        fam_mask = df["famsize"].notna() & df["famsize"].between(1, 20)
        df["famsize_grp"] = pd.NA
        df.loc[fam_mask, "famsize_grp"] = df.loc[fam_mask, "famsize"].apply(
            lambda x: "7+" if x >= 7 else str(int(x))
        )

    # Decade label for trend comparisons
    if "year" in df.columns:
        df["decade"] = (df["year"] // 10 * 10).astype("Int64").astype(str) + "s"

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "gss_clean.parquet"
    df.to_parquet(out, index=False)
    print(f"  GSS: {len(df):,} rows -> {out}")
    return df
