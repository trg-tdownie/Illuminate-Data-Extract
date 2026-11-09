#!/usr/bin/env python3
"""
Illuminate Data Weekly Update Script
Runs every Monday to pull the last week's data and update all tables

This script:
1. Reloads the current school year's assessment results (other years are left alone)
   - Uses section-based teacher matching via LPC_StudentRoster
   - Matches students to their actual subject teacher (not homeroom)
2. Updates Illuminate_Assignments lookup table
3. Updates Illuminate_Standards lookup table
4. Rebuilds that year's rows in Illuminate_Assessment_Summary

Usage:
  python3 weekly_update.py                            # Current school year
  python3 weekly_update.py --school-year 2025-2026    # Reload a closed year from its own records
"""

from illuminate_extractor import IlluminateAPIExtractor
from datetime import datetime, timedelta
import pyodbc
import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyUpdater:
    def __init__(self, config_file='config.ini'):
        self.extractor = IlluminateAPIExtractor(config_file)
        self.db_connection = None

    def connect_db(self):
        """Connect to SQL Server database."""
        try:
            conn_str = (
                r'DRIVER={ODBC Driver 17 for SQL Server};'
                r'SERVER=10.10.10.200;'
                r'DATABASE=TRG_Dashboard;'
                r'UID=trg-dashboard;'
                r'PWD=qptpP<xf/rv#:5S;'
            )
            self.db_connection = pyodbc.connect(conn_str)
            logger.info("Connected to SQL Server database")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def update_lookup_tables(self):
        """Update Illuminate_Assignments and Illuminate_Standards lookup tables."""
        if not self.db_connection:
            return False

        try:
            cursor = self.db_connection.cursor()

            # Update Assignments
            logger.info("Updating Illuminate_Assignments lookup table...")
            cursor.execute("""
                MERGE Illuminate_Assignments AS target
                USING (
                    SELECT
                        AssessmentID,
                        AssignmentName,
                        Subject,
                        ProgramName,
                        Publisher,
                        Component,
                        SchoolID
                    FROM (
                        SELECT
                            AssessmentID,
                            AssignmentName,
                            Subject,
                            ProgramName,
                            Publisher,
                            Component,
                            SchoolID,
                            ROW_NUMBER() OVER (
                                PARTITION BY
                                    COALESCE(ProgramName, ''),
                                    COALESCE(Component, ''),
                                    COALESCE(AssignmentName, ''),
                                    SchoolID
                                ORDER BY AssessmentID
                            ) as rn
                        FROM (
                            SELECT DISTINCT
                                AssessmentID,
                                AssignmentName,
                                COALESCE(
                                    Subject,
                                    CASE
                                        WHEN StandardCodingNumber LIKE 'ELA%' THEN 'ELA'
                                        WHEN StandardCodingNumber LIKE 'Math%' THEN 'Math'
                                        WHEN StandardCodingNumber LIKE 'CCSS.ELA%' THEN 'ELA'
                                        WHEN StandardCodingNumber LIKE 'CCSS.Math%' THEN 'Math'
                                        ELSE NULL
                                    END
                                ) as Subject,
                                ProgramName,
                                Publisher,
                                Component,
                                SchoolID
                            FROM Illuminate_Assessment_Results
                            WHERE AssessmentID IS NOT NULL
                            AND SchoolID IS NOT NULL
                        ) r1
                    ) deduplicated
                    WHERE rn = 1
                ) AS source
                ON (
                    ISNULL(target.ProgramName, '') = ISNULL(source.ProgramName, '')
                    AND ISNULL(target.Component, '') = ISNULL(source.Component, '')
                    AND ISNULL(target.AssignmentName, '') = ISNULL(source.AssignmentName, '')
                    AND target.SchoolID = source.SchoolID
                )
                WHEN MATCHED THEN
                    UPDATE SET
                        target.AssignmentName = COALESCE(source.AssignmentName, target.AssignmentName),
                        target.Subject = COALESCE(source.Subject, target.Subject),
                        target.ProgramName = COALESCE(source.ProgramName, target.ProgramName),
                        target.Publisher = COALESCE(source.Publisher, target.Publisher),
                        target.Component = COALESCE(source.Component, target.Component)
                WHEN NOT MATCHED THEN
                    INSERT (
                        IlluminateAssessmentID,
                        AssignmentName,
                        Subject,
                        ProgramName,
                        Publisher,
                        Component,
                        SchoolID
                    )
                    VALUES (
                        source.AssessmentID,
                        source.AssignmentName,
                        source.Subject,
                        source.ProgramName,
                        source.Publisher,
                        source.Component,
                        source.SchoolID
                    );
            """)
            assignments_updated = cursor.rowcount
            self.db_connection.commit()
            logger.info(f"Updated {assignments_updated} assignments")

            # Update Standards
            logger.info("Updating Illuminate_Standards lookup table...")
            cursor.execute("""
                MERGE Illuminate_Standards AS target
                USING (
                    SELECT DISTINCT
                        StandardCodingNumber,
                        StandardDescription,
                        CASE
                            WHEN StandardCodingNumber LIKE 'ELA%' THEN 'ELA'
                            WHEN StandardCodingNumber LIKE 'Math%' THEN 'Math'
                            WHEN StandardCodingNumber LIKE 'CCSS.ELA%' THEN 'ELA'
                            WHEN StandardCodingNumber LIKE 'CCSS.Math%' THEN 'Math'
                            ELSE NULL
                        END as Subject
                    FROM Illuminate_Assessment_Results
                    WHERE StandardCodingNumber IS NOT NULL
                      AND StandardCodingNumber <> ''
                ) AS source
                ON target.StandardCodingNumber = source.StandardCodingNumber
                WHEN MATCHED THEN
                    UPDATE SET
                        target.StandardDescription = COALESCE(source.StandardDescription, target.StandardDescription),
                        target.Subject = COALESCE(source.Subject, target.Subject)
                WHEN NOT MATCHED THEN
                    INSERT (
                        StandardCodingNumber,
                        StandardDescription,
                        Subject
                    )
                    VALUES (
                        source.StandardCodingNumber,
                        source.StandardDescription,
                        source.Subject
                    );
            """)
            standards_updated = cursor.rowcount
            self.db_connection.commit()
            logger.info(f"Updated {standards_updated} standards")

            cursor.close()
            return True

        except Exception as e:
            logger.error(f"Failed to update lookup tables: {e}")
            return False

    def rebuild_summary_table(self, school_year):
        """Rebuild one school year of Illuminate_Assessment_Summary from the results table.

        Only that year: the results for other years weren't reloaded, so neither are their summaries.
        """
        if not self.db_connection:
            return False

        try:
            cursor = self.db_connection.cursor()

            logger.info(f"Clearing {school_year} from Illuminate_Assessment_Summary...")
            cursor.execute("DELETE FROM Illuminate_Assessment_Summary WHERE AcademicYear = ?", school_year)
            self.db_connection.commit()

            logger.info(f"Rebuilding {school_year} summary from assessment results...")
            cursor.execute("""
                INSERT INTO Illuminate_Assessment_Summary (
                    AcademicYear, SchoolName,
                    StudentID_SASID, StudentID_LASID,
                    LastName, FirstName, StudentGrade,
                    ClassName, TeacherLastName, TeacherFirstName,
                    Subject, ProgramName, Publisher, Component, AssignmentName,
                    AssessmentID, DateCompleted, StandardSet,
                    TotalPointsAchieved, TotalPointsPossible, OverallPercentCorrect,
                    SchoolID
                )
                SELECT
                    AcademicYear,
                    SchoolName,
                    StudentID_SASID,
                    StudentID_LASID,
                    LastName,
                    FirstName,
                    StudentGrade,
                    ClassName,
                    TeacherLastName,
                    TeacherFirstName,
                    -- Derive subject from AssignmentName when missing
                    CASE
                        WHEN AssignmentName LIKE '%Math%' OR AssignmentName LIKE '%math%' THEN 'Mathematics'
                        WHEN AssignmentName LIKE '%ELA%' OR AssignmentName LIKE '%ela%' OR AssignmentName LIKE '%English%' THEN 'English Language Arts'
                        WHEN AssignmentName LIKE '%Science%' OR AssignmentName LIKE '%science%' THEN 'Science'
                        WHEN AssignmentName LIKE '%Social%' OR AssignmentName LIKE '%History%' THEN 'Social Studies'
                        ELSE Subject
                    END as Subject,
                    ProgramName,
                    Publisher,
                    Component,
                    AssignmentName,
                    AssessmentID,
                    DateCompleted,
                    NULL as StandardSet,
                    SUM(PointsAchieved) as TotalPointsAchieved,
                    SUM(PointsPossible) as TotalPointsPossible,
                    CASE
                        WHEN SUM(PointsPossible) > 0
                        THEN FORMAT(CAST(SUM(PointsAchieved) AS FLOAT) / SUM(PointsPossible) * 100, '0.000000') + '%'
                        ELSE NULL
                    END as OverallPercentCorrect,
                    SchoolID
                FROM Illuminate_Assessment_Results
                WHERE AssessmentID IS NOT NULL
                  AND StudentID_SASID IS NOT NULL
                  AND AcademicYear = ?
                GROUP BY
                    AcademicYear, SchoolName,
                    StudentID_SASID, StudentID_LASID,
                    LastName, FirstName, StudentGrade,
                    ClassName, TeacherLastName, TeacherFirstName,
                    -- Include CASE statement in GROUP BY
                    CASE
                        WHEN AssignmentName LIKE '%Math%' OR AssignmentName LIKE '%math%' THEN 'Mathematics'
                        WHEN AssignmentName LIKE '%ELA%' OR AssignmentName LIKE '%ela%' OR AssignmentName LIKE '%English%' THEN 'English Language Arts'
                        WHEN AssignmentName LIKE '%Science%' OR AssignmentName LIKE '%science%' THEN 'Science'
                        WHEN AssignmentName LIKE '%Social%' OR AssignmentName LIKE '%History%' THEN 'Social Studies'
                        ELSE Subject
                    END,
                    ProgramName, Publisher, Component, AssignmentName,
                    AssessmentID, DateCompleted, SchoolID
                ORDER BY DateCompleted, LastName, FirstName, AssignmentName
            """, school_year)
            summary_count = cursor.rowcount
            self.db_connection.commit()
            logger.info(f"Created {summary_count} summary records")

            cursor.close()
            return True

        except Exception as e:
            logger.error(f"Failed to rebuild summary table: {e}")
            return False

    def run_weekly_update(self, days_back=7, school_year=None):
        """Run complete weekly update process for one school year (default: the current one)."""
        school_year = school_year or self.extractor.current_school_year()

        print("=" * 80)
        print("Illuminate Assessment Data Weekly Update")
        print("=" * 80)

        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        print(f"Date Range: {start_date} to {end_date} ({days_back} days)")
        print(f"School Year: {school_year} (each result labelled by its own date taken)")
        print("=" * 80)
        print()

        # Step 1: Reload this school year's results.
        # Only this year: the API returns every year's results each run, and reloading a closed
        # year from the live roster used to stamp this year's grades, schools and teachers on
        # last year's tests. Other years' rows are left as they are.
        logger.info(f"STEP 1/4: Reloading {school_year} assessment data...")
        total_records = self.extractor.extract_illuminate_assessment_data(
            school_ids=None,
            start_date=start_date,
            end_date=end_date,
            school_year=school_year,
        )
        logger.info(f"Extracted {total_records} assessment records")
        print()

        # Connect to database for remaining steps
        if not self.connect_db():
            logger.error("Failed to connect to database. Aborting update.")
            return False

        # Step 2: Update lookup tables
        logger.info("STEP 2/4: Updating lookup tables...")
        if not self.update_lookup_tables():
            logger.error("Failed to update lookup tables")
            return False
        print()

        # Step 3: Rebuild summary table
        logger.info("STEP 3/4: Rebuilding summary table...")
        if not self.rebuild_summary_table(school_year):
            logger.error("Failed to rebuild summary table")
            return False
        print()

        # Step 4: Verification
        logger.info("STEP 4/4: Verification...")
        cursor = self.db_connection.cursor()

        cursor.execute("SELECT COUNT(*) FROM Illuminate_Assessment_Results")
        results_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Illuminate_Assignments")
        assignments_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Illuminate_Standards")
        standards_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Illuminate_Assessment_Summary")
        summary_count = cursor.fetchone()[0]

        cursor.close()
        self.db_connection.close()

        print()
        print("=" * 80)
        print("WEEKLY UPDATE COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"Illuminate_Assessment_Results:  {results_count:>8,} records")
        print(f"Illuminate_Assignments:         {assignments_count:>8,} records")
        print(f"Illuminate_Standards:           {standards_count:>8,} records")
        print(f"Illuminate_Assessment_Summary:  {summary_count:>8,} records")
        print("=" * 80)
        print()
        print(f"Next update: Run this script again next Monday")
        print("=" * 80)

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Illuminate Assessment Data Weekly Update'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days back to extract (default: 7)'
    )
    parser.add_argument(
        '--school-year',
        default=None,
        help="School year to reload, e.g. 2025-2026 (default: the current one). "
             "A closed year is enriched from that year's own roster and grades."
    )
    args = parser.parse_args()

    updater = WeeklyUpdater()
    success = updater.run_weekly_update(days_back=args.days, school_year=args.school_year)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
