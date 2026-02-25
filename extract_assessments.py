"""
Extract Assessment Metadata from Illuminate API
Populates the Illuminate_Assignments table with assessment information
"""

from illuminate_extractor import IlluminateAPIExtractor
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('assessment_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def extract_assessments():
    """Extract all assessment metadata from Illuminate"""

    print("=" * 80)
    print("Illuminate Assessment Metadata Extractor")
    print("=" * 80)
    print("This extracts assessment information to populate Illuminate_Assignments table")
    print("=" * 80)

    extractor = IlluminateAPIExtractor('config.ini')
    extractor.connect_db()

    try:
        # Get all assessments from the API
        logger.info("Fetching assessments from /Api/Assessments endpoint...")
        page = 1
        total_assessments = 0

        while True:
            params = {
                'page': page,
                'limit': 1000
            }

            data = extractor._make_api_request('/Api/Assessments/', params)

            if not data or 'results' not in data:
                logger.warning(f"No data returned from /Api/Assessments")
                break

            results = data['results']
            if not results:
                break

            logger.info(f"Processing page {page}, found {len(results)} assessments")

            # Process each assessment
            for assessment in results:
                save_assessment(extractor, assessment)
                total_assessments += 1

            # Check if we're done
            if page >= data.get('num_pages', 1):
                break

            page += 1

        logger.info(f"Total assessments processed: {total_assessments}")

        print("=" * 80)
        print(f"Assessment extraction completed!")
        print(f"Total assessments processed: {total_assessments}")
        print("=" * 80)

    finally:
        extractor.disconnect_db()


def save_assessment(extractor, assessment):
    """Save a single assessment to Illuminate_Assignments table"""

    if not extractor.db_connection:
        return

    try:
        cursor = extractor.db_connection.cursor()

        # Check if this assessment already exists
        assessment_id = assessment.get('assessment_id')

        check_query = """
            SELECT COUNT(*) FROM Illuminate_Assignments
            WHERE IlluminateAssessmentID = ?
        """

        cursor.execute(check_query, (assessment_id,))
        exists = cursor.fetchone()[0] > 0

        if exists:
            logger.debug(f"Assessment {assessment_id} already exists, skipping")
            cursor.close()
            return

        # Extract relevant fields
        program_name = None  # Not provided by this endpoint
        publisher = assessment.get('publisher')  # Not provided
        component = assessment.get('scope')  # Use scope as component
        assignment_name = assessment.get('title') or assessment.get('name')
        subject = assessment.get('subject') or assessment.get('subject_name')

        # Try to extract program name from title if it follows a pattern
        # e.g., "3ELAMOD1" might be "3rd Grade ELA Module 1"
        if assignment_name and 'ELA' in assignment_name.upper():
            program_name = 'ELA'
        elif assignment_name and 'MATH' in assignment_name.upper():
            program_name = 'Math'

        # Insert the assessment
        query = """
            INSERT INTO Illuminate_Assignments (
                ProgramName,
                Publisher,
                Component,
                AssignmentName,
                IlluminateAssessmentID,
                Subject
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """

        values = (
            program_name,
            publisher,
            component,
            assignment_name,
            assessment_id,
            subject
        )

        cursor.execute(query, values)
        extractor.db_connection.commit()
        cursor.close()

        logger.info(f"Saved assessment: {assignment_name} (ID: {assessment_id})")

    except Exception as e:
        logger.error(f"Failed to save assessment: {e}")
        logger.error(f"Assessment data: {assessment}")


def test_assessments_endpoint():
    """Test the assessments endpoint to see what data is available"""

    print("=" * 80)
    print("Testing /Api/Assessments endpoint...")
    print("=" * 80)

    extractor = IlluminateAPIExtractor('config.ini')

    # Test with a small request
    params = {
        'page': 1,
        'limit': 5
    }

    data = extractor._make_api_request('/Api/Assessments/', params)

    if data and 'results' in data:
        print(f"\nTotal assessments available: {data.get('num_results', 0)}")
        print(f"Number of pages: {data.get('num_pages', 0)}")
        print("\nSample assessment data:")
        print("-" * 80)

        import json
        for i, assessment in enumerate(data['results'][:3], 1):
            print(f"\nAssessment {i}:")
            print(json.dumps(assessment, indent=2))
            print("-" * 80)
    else:
        print("No assessments found or endpoint returned no data")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Test mode - just show what's available
        test_assessments_endpoint()
    else:
        # Full extraction
        extract_assessments()
