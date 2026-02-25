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

    # Determine academic year
    current_month = datetime.now().month
    current_year = datetime.now().year
    if current_month >= 7:  # July onwards
        academic_year = f"{current_year}-{current_year + 1}"
    else:  # January to June
        academic_year = f"{current_year - 1}-{current_year}"

    print("=" * 80)
    print("Illuminate Assessment Data Incremental Extractor")
    print("=" * 80)
    print(f"Extracting data from the last {days_back} days")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Academic Year: {academic_year}")
    print("=" * 80)

    # Run incremental extraction
    total_records = extractor.extract_illuminate_assessment_data(
        school_ids=None,
        start_date=start_date,
        end_date=end_date,
        academic_year=academic_year
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
