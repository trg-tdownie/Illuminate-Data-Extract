#!/usr/bin/env python3
"""
Illuminate Data Weekly Update Script
Runs every Monday to pull the last week's data and update all tables

This script:
1. Extracts assessment data from the last 7 days
   - Uses section-based teacher matching via LPC_StudentRoster
   - Matches students to their actual subject teacher (not homeroom)
2. Updates Illuminate_Assignments lookup table
3. Updates Illuminate_Standards lookup table
4. Rebuilds Illuminate_Assessment_Summary table

Usage:
  python3 weekly_update.py              # Last 7 days
  python3 weekly_update.py --days 14    # Last 14 days
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

    def rebuild_summary_table(self):
        """Rebuild Illuminate_Assessment_Summary from results table."""
        if not self.db_connection:
            return False

        try:
            cursor = self.db_connection.cursor()

            logger.info("Clearing Illuminate_Assessment_Summary...")
            cursor.execute("TRUNCATE TABLE Illuminate_Assessment_Summary")
            self.db_connection.commit()

            logger.info("Rebuilding summary from assessment results...")
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
            """)
            summary_count = cursor.rowcount
            self.db_connection.commit()
            logger.info(f"Created {summary_count} summary records")

            cursor.close()
            return True

        except Exception as e:
            logger.error(f"Failed to rebuild summary table: {e}")
            return False

    def run_weekly_update(self, days_back=7):
        """Run complete weekly update process."""
        print("=" * 80)
        print("Illuminate Assessment Data Weekly Update")
        print("=" * 80)

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

        print(f"Date Range: {start_date} to {end_date} ({days_back} days)")
        print(f"Academic Year: {academic_year}")
        print("=" * 80)
        print()

        # Step 1: Extract recent assessment data
        logger.info("STEP 1/4: Extracting recent assessment data...")
        total_records = self.extractor.extract_illuminate_assessment_data(
            school_ids=None,
            start_date=start_date,
            end_date=end_date,
            academic_year=academic_year
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
        if not self.rebuild_summary_table():
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
    args = parser.parse_args()

    updater = WeeklyUpdater()
    success = updater.run_weekly_update(days_back=args.days)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
