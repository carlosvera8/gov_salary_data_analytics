"""
Pull Census ACS 1-Year Estimates: income, earnings, and demographics.
Coverage: 2010–2023 (2020 skipped — Census did not release ACS 1-year that year due to COVID).
Geography: national + all metro areas with population >= 65,000.

Two API calls are made per year/geography to stay under the 50-variable-per-request limit:
  - VARIABLES: core income + demographics
  - OCC_VARIABLES: median earnings by major occupation group (B24011/B24021/B24031)
"""
import os
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY", "")
BASE_URL = "https://api.census.gov/data/{year}/acs/acs1"
RAW_DIR = Path("data/raw/census")

# ACS 1-Year releases (2020 not published due to COVID data quality issues)
YEARS = [y for y in range(2010, 2024) if y != 2020]

# Census API variable codes -> readable column names.
# All income/earnings variables are in current-year dollars; clean.py applies CPI adjustment.
VARIABLES = {
    # Median earnings for all workers 16+ with earnings
    "B20002_001E": "median_earnings_total",
    "B20002_002E": "median_earnings_male",
    "B20002_003E": "median_earnings_female",
    # Median earnings for full-time, year-round workers (better gender comparison)
    "B20004_001E": "median_ftyr_total",
    "B20004_002E": "median_ftyr_male",
    "B20004_003E": "median_ftyr_female",
    # Median household income
    "B19013_001E": "median_hhi",
    # Median HH income by race/ethnicity
    "B19013A_001E": "median_hhi_white",
    "B19013B_001E": "median_hhi_black",
    "B19013C_001E": "median_hhi_aian",
    "B19013D_001E": "median_hhi_asian",
    "B19013H_001E": "median_hhi_white_nh",
    "B19013I_001E": "median_hhi_hispanic",
    # Median earnings by race/ethnicity — B20017A-I (ACS 1-year table)
    # _001E=total, _002E=male, _005E=female (per variable label metadata)
    "B20017A_001E": "median_earn_white",
    "B20017A_002E": "median_earn_white_male",
    "B20017A_005E": "median_earn_white_female",
    "B20017B_001E": "median_earn_black",
    "B20017B_002E": "median_earn_black_male",
    "B20017B_005E": "median_earn_black_female",
    "B20017D_001E": "median_earn_asian",
    "B20017D_002E": "median_earn_asian_male",
    "B20017D_005E": "median_earn_asian_female",
    "B20017H_001E": "median_earn_white_nh",
    "B20017H_002E": "median_earn_white_nh_male",
    "B20017H_005E": "median_earn_white_nh_female",
    "B20017I_001E": "median_earn_hispanic",
    "B20017I_002E": "median_earn_hispanic_male",
    "B20017I_005E": "median_earn_hispanic_female",
    # Median family income by family size (B19119)
    "B19119_002E": "median_faminc_2person",
    "B19119_003E": "median_faminc_3person",
    "B19119_004E": "median_faminc_4person",
    "B19119_005E": "median_faminc_5person",
    "B19119_006E": "median_faminc_6person",
    "B19119_007E": "median_faminc_7plus",
    # Total population
    "B01003_001E": "total_population",
}

# Median earnings by major occupation group — B24011 (all workers), B24021 (male)
OCC_VARIABLES = {
    # All workers — B24011
    "B24011_001E": "occ_earn_total",
    "B24011_002E": "occ_earn_mgmt_sci_arts",
    "B24011_003E": "occ_earn_mgmt_biz_fin",
    "B24011_006E": "occ_earn_computer_eng_sci",
    "B24011_010E": "occ_earn_edu_legal_arts",
    "B24011_015E": "occ_earn_healthcare_pract",
    "B24011_018E": "occ_earn_service",
    "B24011_026E": "occ_earn_sales_office",
    "B24011_029E": "occ_earn_construction",
    "B24011_033E": "occ_earn_production_transport",
    # Male workers — B24021
    "B24021_001E": "occ_earn_male_total",
    "B24021_002E": "occ_earn_male_mgmt_sci_arts",
    "B24021_018E": "occ_earn_male_service",
    "B24021_026E": "occ_earn_male_sales_office",
    "B24021_029E": "occ_earn_male_construction",
    "B24021_033E": "occ_earn_male_production_transport",
}

# Median earnings by industry — B24031 (all workers), B24032 (male workers)
# No female-by-industry table in ACS 1-year; gap = B24031 - B24032 gives implied female
IND_VARIABLES = {
    # All workers — B24031
    "B24031_001E": "ind_earn_total",
    "B24031_005E": "ind_earn_construction",
    "B24031_006E": "ind_earn_manufacturing",
    "B24031_007E": "ind_earn_wholesale",
    "B24031_008E": "ind_earn_retail",
    "B24031_009E": "ind_earn_transport_utilities",
    "B24031_012E": "ind_earn_information",
    "B24031_013E": "ind_earn_finance_realestate",
    "B24031_014E": "ind_earn_finance_insurance",
    "B24031_016E": "ind_earn_professional_sci",
    "B24031_017E": "ind_earn_professional_sci_tech",
    "B24031_020E": "ind_earn_edu_healthcare",
    "B24031_021E": "ind_earn_education",
    "B24031_022E": "ind_earn_healthcare",
    "B24031_023E": "ind_earn_arts_food",
    "B24031_025E": "ind_earn_accommodation_food",
    "B24031_026E": "ind_earn_other_services",
    "B24031_027E": "ind_earn_public_admin",
    # Male workers — B24032
    "B24032_001E": "ind_earn_male_total",
    "B24032_005E": "ind_earn_male_construction",
    "B24032_006E": "ind_earn_male_manufacturing",
    "B24032_008E": "ind_earn_male_retail",
    "B24032_012E": "ind_earn_male_information",
    "B24032_014E": "ind_earn_male_finance_insurance",
    "B24032_017E": "ind_earn_male_professional_sci_tech",
    "B24032_022E": "ind_earn_male_healthcare",
    "B24032_027E": "ind_earn_male_public_admin",
}

# Census uses this sentinel for suppressed/unavailable cells
CENSUS_NA = -666666666


def _get(url: str, params: dict) -> pd.DataFrame:
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    # Census returns HTML (not JSON) when the key is invalid or not yet activated
    if resp.text.strip().startswith("<"):
        if "Invalid Key" in resp.text:
            raise RuntimeError(
                "Census API key is invalid. Check that CENSUS_API_KEY in .env matches "
                "the key from your Census email exactly. New keys can take a few minutes to activate."
            )
        raise RuntimeError(f"Census API returned unexpected HTML. Response: {resp.text[:200]}")
    data = resp.json()
    return pd.DataFrame(data[1:], columns=data[0])


def _add_meta(df: pd.DataFrame, year: int, geography: str, geo_id_col: str | None = None) -> pd.DataFrame:
    df = df.rename(columns=VARIABLES)
    df["year"] = year
    df["geography"] = geography
    if geo_id_col and geo_id_col in df.columns:
        df["geo_id"] = df[geo_id_col]
        df = df.drop(columns=[geo_id_col])
    else:
        df["geo_id"] = geography
    return df


def _fetch_vars(url: str, vars_dict: dict, geo_params: dict) -> pd.DataFrame:
    vars_str = ",".join(vars_dict.keys())
    params = {"get": vars_str, "key": CENSUS_API_KEY, **geo_params}
    df = _get(url, params)
    return df.rename(columns=vars_dict)


def _merge_extra(core: pd.DataFrame, extra_vars: dict, raw: pd.DataFrame) -> pd.DataFrame:
    """Merge extra variable columns (already renamed) into core by row position."""
    for col in extra_vars.values():
        if col in raw.columns:
            core[col] = raw[col].values
    return core


def _fetch_extra(url: str, vars_dict: dict, geo_params: dict, geo_id_col: str | None = None) -> pd.DataFrame | None:
    try:
        extra_cols = ",".join(vars_dict.keys())
        if geo_id_col:
            extra_cols += f",{geo_id_col}"
        params = {"get": extra_cols, "key": CENSUS_API_KEY, **geo_params}
        df = _get(url, params).rename(columns=vars_dict)
        return df
    except Exception:
        return None  # table may not exist for older years


def fetch_national(year: int) -> pd.DataFrame:
    url = BASE_URL.format(year=year)
    geo = {"for": "us:1"}
    core = _fetch_vars(url, VARIABLES, geo)
    core = _add_meta(core, year, "National")
    core["NAME"] = "United States"
    for extra in [OCC_VARIABLES, IND_VARIABLES]:
        raw = _fetch_extra(url, extra, geo)
        if raw is not None:
            core = _merge_extra(core, extra, raw)
    return core


def fetch_metro(year: int) -> pd.DataFrame:
    url = BASE_URL.format(year=year)
    geo_param = "metropolitan statistical area/micropolitan statistical area"
    geo = {"for": f"{geo_param}:*"}
    core = _get(url, {"get": ",".join(VARIABLES.keys()) + ",NAME", "key": CENSUS_API_KEY, **geo})
    core = core.rename(columns=VARIABLES)
    core = _add_meta(core, year, "Metro", geo_id_col=geo_param)
    for extra in [OCC_VARIABLES, IND_VARIABLES]:
        raw = _fetch_extra(url, extra, geo, geo_id_col=geo_param)
        if raw is not None:
            core = _merge_extra(core, extra, raw)
    return core


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    all_value_cols = list(VARIABLES.values()) + list(OCC_VARIABLES.values()) + list(IND_VARIABLES.values())
    for col in all_value_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].where((df[col] > 0) & (df[col] != CENSUS_NA))
    return df


def pull_all() -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    frames = []

    for year in YEARS:
        print(f"  ACS {year}...")
        for label, fn in [("national", fetch_national), ("metro", fetch_metro)]:
            try:
                frames.append(fn(year))
            except Exception as exc:
                print(f"    {label} {year} skipped: {exc}")
        time.sleep(0.3)  # stay well within Census rate limits

    df = pd.concat(frames, ignore_index=True)
    df = _coerce_numeric(df)

    out = RAW_DIR / "acs_income_demographics.parquet"
    df.to_parquet(out, index=False)
    print(f"  Saved {len(df):,} rows -> {out}")
    return df
