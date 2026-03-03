#!/usr/bin/env python3
"""
Weekly Illuminate Data Update Script

This script performs the complete weekly update workflow:
1. Runs incremental extraction (last 7 days by default)
2. Populates/updates lookup tables (Assignments and Standards)

Can be scheduled to run weekly via cron or Windows Task Scheduler.
"""

import subprocess
import sys
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'weekly_update_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DAYS_BACK = 7  # How many days of data to extract


def run_command(command: list, description: str) -> bool:
    """Run a command and return True if successful."""
    logger.info("=" * 80)
    logger.info(f"Starting: {description}")
    logger.info("=" * 80)
    logger.info(f"Command: {' '.join(command)}")
    logger.info("")

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        logger.info(f"✓ Success: {description} completed")
        logger.info("")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Error: {description} failed")
        logger.error(f"Exit code: {e.returncode}")
        if e.stdout:
            logger.error(f"Output: {e.stdout}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error in {description}: {e}")
        return False


def main():
    """Run the complete weekly update workflow."""
    start_time = datetime.now()

    logger.info("")
    logger.info("=" * 80)
    logger.info("ILLUMINATE WEEKLY DATA UPDATE")
    logger.info("=" * 80)
    logger.info(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Extracting last {DAYS_BACK} days of data")
    logger.info("=" * 80)
    logger.info("")

    # Get script directory
    script_dir = Path(__file__).parent

    # Step 1: Run incremental extraction
    extraction_script = script_dir / "illuminate_extractor_incremental.py"
    if not extraction_script.exists():
        logger.error(f"Extraction script not found: {extraction_script}")
        sys.exit(1)

    success = run_command(
        [sys.executable, str(extraction_script), str(DAYS_BACK)],
        f"Step 1/2: Incremental Extraction (last {DAYS_BACK} days)"
    )

    if not success:
        logger.error("Extraction failed. Stopping workflow.")
        logger.error("Lookup tables will NOT be updated.")
        sys.exit(1)

    # Step 2: Populate lookup tables
    populate_script = script_dir / "populate_lookup_tables.py"
    if not populate_script.exists():
        logger.error(f"Populate script not found: {populate_script}")
        sys.exit(1)

    success = run_command(
        [sys.executable, str(populate_script)],
        "Step 2/2: Populate Lookup Tables"
    )

    if not success:
        logger.error("Lookup table population failed.")
        logger.warning("Extraction completed successfully, but lookup tables may be out of sync.")
        sys.exit(1)

    # Success!
    end_time = datetime.now()
    duration = end_time - start_time

    logger.info("")
    logger.info("=" * 80)
    logger.info("✓ WEEKLY UPDATE COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)
    logger.info(f"Started:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Duration: {duration}")
    logger.info("")
    logger.info("Summary:")
    logger.info(f"  ✓ Incremental extraction (last {DAYS_BACK} days)")
    logger.info("  ✓ Illuminate_Assignments updated")
    logger.info("  ✓ Illuminate_Standards updated")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  - Verify data in your database")
    logger.info("  - Check the log file for details")
    logger.info("  - Schedule this script to run weekly")
    logger.info("")
    logger.info("To schedule this script:")
    logger.info("  macOS/Linux: Add to crontab (run 'crontab -e'):")
    logger.info(f"    0 2 * * 1 {sys.executable} {Path(__file__).absolute()}")
    logger.info("    (Runs every Monday at 2 AM)")
    logger.info("")
    logger.info("  Windows: Use Task Scheduler to run this script weekly")
    logger.info("=" * 80)
    logger.info("")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
