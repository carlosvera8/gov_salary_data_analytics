"""
Pull all data and prepare the dashboard.

Data sources:
  - US Census Bureau ACS 1-Year Estimates (2010-2023) via Census API
  - GSS General Social Survey (optional — requires manual CSV download)

Usage:
  python main.py                  # Census pull + process
  python main.py --skip-census    # skip Census pull (re-use existing raw file)
  python main.py --skip-process   # skip cleaning step
  python main.py --gss            # also process GSS happiness data
  python main.py --gss-only       # only process GSS (skip Census)
"""
import sys
from src.ingest import census_acs
from src.process import clean


def main() -> None:
    args = sys.argv[1:]
    skip_census  = "--skip-census"  in args
    skip_process = "--skip-process" in args
    include_gss  = "--gss"          in args or "--gss-only" in args
    gss_only     = "--gss-only"     in args

    print("=" * 50)
    print("  US Government Salary Data -- Pull & Process")
    print("=" * 50)
    print()

    if not skip_census and not gss_only:
        print("[Census] ACS 2010-2023, national + ~530 metros...")
        census_acs.pull_all()
        print()

    if not skip_process and not gss_only:
        print("[Census] Cleaning and inflation-adjusting...")
        clean.clean_census()
        print()

    if include_gss:
        print("[GSS] Processing happiness data...")
        try:
            clean.clean_gss()
        except FileNotFoundError as exc:
            print(f"  Skipped: {exc}")
        print()

    print("=" * 50)
    print("  Done! Start the dashboard:")
    print()
    print("  streamlit run src/dashboard/app.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
