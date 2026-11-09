"""
Illuminate API Incremental Data Extractor
Extracts only recent assessment data (last N days) for daily/nightly updates
"""

from illuminate_extractor import IlluminateAPIExtractor
from datetime import datetime, timedelta
import sys

def main():
    """Run incremental extraction for recent data"""

    # Initialize extractor
    extractor = IlluminateAPIExtractor('config.ini')

    # Configuration for incremental extraction
    # Extract last 7 days by default (can be overridden via command line)
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    # Calculate date range
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    # Reload the current school year only. This used to work out a year here (rolling over on
    # 1 July) and pass it as the label for EVERY row, which stamped it on prior years' results.
    # The extractor now labels each row by its own date and leaves other years alone.
    school_year = extractor.current_school_year()

    print("=" * 80)
    print("Illuminate Assessment Data Incremental Extractor")
    print("=" * 80)
    print(f"Extracting data from the last {days_back} days")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"School Year: {school_year}")
    print("=" * 80)

    # Run incremental extraction
    total_records = extractor.extract_illuminate_assessment_data(
        school_ids=None,
        start_date=start_date,
        end_date=end_date,
        school_year=school_year
    )

    print("=" * 80)
    print(f"Incremental extraction completed successfully!")
    print(f"Total assessment records extracted: {total_records}")
    print("=" * 80)
    print()
    print("To run this script:")
    print("  - Daily update (last 7 days): python illuminate_extractor_incremental.py")
    print("  - Custom days back: python illuminate_extractor_incremental.py 3")
    print("=" * 80)


if __name__ == "__main__":
    main()
