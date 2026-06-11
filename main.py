"""
Pull all data and prepare the dashboard.

Data sources:
  - US Census Bureau ACS 1-Year Estimates (2010-2023) via Census API
    Covers: income by race, gender, family size, occupation, metro area

Usage:
  python main.py                # full pull + process
  python main.py --skip-census  # skip Census pull (re-use existing raw file)
  python main.py --skip-process # skip cleaning step
"""
import sys
from src.ingest import census_acs
from src.process import clean


def main() -> None:
    args = sys.argv[1:]
    skip_census  = "--skip-census"  in args
    skip_process = "--skip-process" in args

    print("=" * 50)
    print("  US Government Salary Data — Pull & Process")
    print("=" * 50)
    print()

    if not skip_census:
        print("[1/2] Census ACS (2010–2023, national + ~530 metros)...")
        census_acs.pull_all()
        print()

    if not skip_process:
        print("[2/2] Cleaning and inflation-adjusting...")
        clean.clean_census()
        print()

    print("=" * 50)
    print("  Done! Start the dashboard:")
    print()
    print("  streamlit run src/dashboard/app.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
