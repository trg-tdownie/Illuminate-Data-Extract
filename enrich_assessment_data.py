"""
Enrich Assessment Results with Teacher Names and Grade Levels
Updates existing Illuminate_Assessment_Results records with:
- Teacher first and last names
- Student grade levels
- Class/section information
"""

from illuminate_extractor import IlluminateAPIExtractor
import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enrichment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_users_cache(extractor):
    """Load all users (teachers) into cache"""
    logger.info("Loading users/teachers into cache...")
    users_cache = {}
    page = 1

    while True:
        params = {'page': page, 'limit': 1000}
        data = extractor._make_api_request('/Api/Users/', params)

        if not data or 'results' not in data:
            break

        results = data['results']
        if not results:
            break

        for user in results:
            user_id = user.get('user_id')
            if user_id:
                users_cache[str(user_id)] = {
                    'first_name': user.get('first_name'),
                    'last_name': user.get('last_name'),
                    'job_title': user.get('job_title')
                }

        logger.info(f"Loaded page {page} of users, total cached: {len(users_cache)}")

        if page >= data.get('num_pages', 1):
            break

        page += 1
        time.sleep(0.2)

    logger.info(f"Finished loading {len(users_cache)} users")
    return users_cache


def load_roster_cache(extractor):
    """Load roster (student-to-teacher assignments) into cache"""
    logger.info("Loading roster data (student-teacher assignments)...")
    roster_cache = {}
    page = 1

    while True:
        params = {'page': page, 'limit': 1000}
        data = extractor._make_api_request('/Api/Roster/', params)

        if not data or 'results' not in data:
            break

        results = data['results']
        if not results:
            break

        for record in results:
            district_student_id = record.get('district_student_id')
            if district_student_id:
                # Store by student ID - may have multiple sections, we'll use first one
                if str(district_student_id) not in roster_cache:
                    roster_cache[str(district_student_id)] = {
                        'user_id': str(record.get('user_id')),
                        'grade_level_id': record.get('grade_level_id'),
                        'section_id': record.get('section_id'),
                        'site_id': record.get('site_id'),
                        'course_id': record.get('course_id')
                    }

        logger.info(f"Loaded page {page} of roster, total cached: {len(roster_cache)}")

        if page >= data.get('num_pages', 1):
            break

        page += 1
        time.sleep(0.2)

    logger.info(f"Finished loading {len(roster_cache)} student-teacher assignments")
    return roster_cache


def update_assessment_results(extractor, users_cache, roster_cache):
    """Update assessment results with teacher and grade info"""
    logger.info("Updating assessment results with teacher and grade information...")

    if not extractor.db_connection:
        logger.error("No database connection")
        return 0

    cursor = extractor.db_connection.cursor()

    # Get all unique students from assessment results that need updating
    query = """
        SELECT DISTINCT StudentID_LASID
        FROM Illuminate_Assessment_Results
        WHERE (TeacherLastName IS NULL OR StudentGrade IS NULL)
        AND StudentID_LASID IS NOT NULL
    """

    cursor.execute(query)
    students_to_update = [row[0] for row in cursor.fetchall()]
    logger.info(f"Found {len(students_to_update)} students needing enrichment")

    updated_count = 0

    for student_id in students_to_update:
        # Get roster info for this student
        roster_info = roster_cache.get(str(student_id), {})
        teacher_id = roster_info.get('user_id')
        grade_level = roster_info.get('grade_level_id')

        # Get teacher info
        teacher_info = users_cache.get(str(teacher_id), {}) if teacher_id else {}
        teacher_first = teacher_info.get('first_name')
        teacher_last = teacher_info.get('last_name')

        # Update all records for this student
        if teacher_first or teacher_last or grade_level:
            update_query = """
                UPDATE Illuminate_Assessment_Results
                SET
                    TeacherFirstName = COALESCE(TeacherFirstName, ?),
                    TeacherLastName = COALESCE(TeacherLastName, ?),
                    StudentGrade = COALESCE(StudentGrade, ?)
                WHERE StudentID_LASID = ?
            """

            cursor.execute(update_query, (
                teacher_first,
                teacher_last,
                grade_level,
                student_id
            ))

            updated_count += cursor.rowcount

        if updated_count % 100 == 0 and updated_count > 0:
            extractor.db_connection.commit()
            logger.info(f"Updated {updated_count} records so far...")

    # Final commit
    extractor.db_connection.commit()
    cursor.close()

    logger.info(f"Total records updated: {updated_count}")
    return updated_count


def main():
    """Main enrichment process"""
    print("=" * 80)
    print("Assessment Results Data Enrichment")
    print("=" * 80)
    print("This adds teacher names and grade levels to existing assessment results")
    print("=" * 80)

    extractor = IlluminateAPIExtractor('config.ini')
    extractor.connect_db()

    try:
        # Load reference data
        users_cache = load_users_cache(extractor)
        roster_cache = load_roster_cache(extractor)

        # Update assessment results
        updated = update_assessment_results(extractor, users_cache, roster_cache)

        print("=" * 80)
        print(f"Enrichment complete!")
        print(f"Total records updated: {updated}")
        print("=" * 80)

    finally:
        extractor.disconnect_db()


if __name__ == "__main__":
    main()
