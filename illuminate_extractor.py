"""
Illuminate API Assessment Data Extractor for HMH Assessments
Extracts HMH assessment data from Illuminate/Renaissance DnA API
with standards-based scoring and stores in SQL Server database
"""

import requests
import json
import pyodbc
import re
from requests_oauthlib import OAuth1Session, OAuth1
from datetime import datetime
import logging
import time
from typing import Dict, List, Optional, Tuple
import configparser
from decimal import Decimal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('illuminate_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IlluminateAPIExtractor:
    """Main class for extracting data from Illuminate API"""

    def __init__(self, config_file: str = 'config.ini'):
        """Initialize the extractor with configuration"""
        self.config = self._load_config(config_file)
        self.base_url = self.config.get('api', 'base_url')
        self.db_connection = None
        self.oauth = None
        self.sites_cache = {}  # Cache for site/school information
        self.students_cache = {}  # Cache for student information
        self.users_cache = {}  # Cache for user/teacher information
        self.roster_cache = {}  # Cache for student-teacher assignments (ALL sections per student)
        self.lpc_roster_cache = {}  # Cache for LPC_StudentRoster (student->section->teacher)
        self.subject_content_map = {}  # Cache for Module_MonthAssignment (subject->valid ContentArea IDs)
        self.section_lookup_index = {}  # Fast O(1) lookup: (student_id, subject_area, content_area) -> section_info
        self.subject_sa_map = {}  # Pre-computed subject abbreviation -> {sa_code, content_areas}
        self._setup_oauth()

    def _load_config(self, config_file: str) -> configparser.ConfigParser:
        """Load configuration from file"""
        config = configparser.ConfigParser()
        config.read(config_file)
        return config

    def _setup_oauth(self):
        """Setup OAuth 1.0 authentication"""
        consumer_key = self.config.get('oauth', 'consumer_key')
        consumer_secret = self.config.get('oauth', 'consumer_secret')
        access_token = self.config.get('oauth', 'access_token')
        access_token_secret = self.config.get('oauth', 'access_token_secret')

        self.oauth = OAuth1(
            consumer_key,
            client_secret=consumer_secret,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret,
            signature_type='auth_header'
        )
        logger.info("OAuth 1.0 authentication configured")

    def _load_sites_cache(self):
        """Load all sites/schools into cache for lookup"""
        logger.info("Loading sites/schools into cache...")

        sites_data = self._make_api_request('/Api/Sites')
        if sites_data:
            for site in sites_data:
                site_id = site.get('site_id')
                if site_id:
                    self.sites_cache[str(site_id)] = {
                        'site_name': site.get('site_name'),
                        'state_school_id': site.get('state_school_id'),
                        'local_site_code': site.get('local_site_code'),
                        'city': site.get('city'),
                        'state': site.get('state')
                    }
            logger.info(f"Loaded {len(self.sites_cache)} sites into cache")
        else:
            logger.warning("Failed to load sites cache")

    def _load_students_cache(self):
        """Load all students with enrollment/school info into cache for lookup"""
        logger.info("Loading student enrollments with school info into cache...")
        page = 1

        while True:
            params = {
                'page': page,
                'limit': 1000
            }

            # Use Enrollment endpoint which includes school information
            enrollment_data = self._make_api_request('/Api/Enrollment/', params)
            if not enrollment_data or 'results' not in enrollment_data:
                break

            results = enrollment_data['results']
            if not results:
                break

            for enrollment in results:
                # Try multiple ID fields to match assessment data
                district_student_id = enrollment.get('district_student_id')
                state_student_id = enrollment.get('state_student_id')
                student_id = enrollment.get('student_id')

                # Cache by district_student_id (which matches local_student_id in assessments)
                if district_student_id:
                    site_id = enrollment.get('site_id')
                    # Convert grade_level_id to actual grade (K=1, 1st=2, etc. -> K, 1, 2, etc.)
                    grade_level_id = enrollment.get('grade_level_id')
                    actual_grade = self._convert_grade_level_id(grade_level_id)
                    self.students_cache[str(district_student_id)] = {
                        'state_student_id': state_student_id,
                        'student_id': student_id,
                        'grade_level': actual_grade,
                        'site_id': str(site_id) if site_id else None,
                        'site_name': enrollment.get('school'),  # Enrollment API returns 'school' field
                        'district_name': enrollment.get('district')
                    }

            logger.info(f"Loaded page {page} of enrollments, total cached: {len(self.students_cache)}")

            if page >= enrollment_data.get('num_pages', 1):
                break

            page += 1
            time.sleep(0.2)  # Rate limiting

        logger.info(f"Finished loading {len(self.students_cache)} student enrollments into cache")

    def _load_users_cache(self):
        """Load all users (teachers) into cache"""
        logger.info("Loading users/teachers into cache...")
        page = 1

        while True:
            params = {'page': page, 'limit': 1000}
            data = self._make_api_request('/Api/Users/', params)

            if not data or 'results' not in data:
                break

            results = data['results']
            if not results:
                break

            for user in results:
                user_id = user.get('user_id')
                if user_id:
                    self.users_cache[str(user_id)] = {
                        'first_name': user.get('first_name'),
                        'last_name': user.get('last_name'),
                        'job_title': user.get('job_title')
                    }

            logger.info(f"Loaded page {page} of users, total cached: {len(self.users_cache)}")

            if page >= data.get('num_pages', 1):
                break

            page += 1
            time.sleep(0.2)

        logger.info(f"Finished loading {len(self.users_cache)} users")

    def _load_roster_cache(self):
        """Load roster (student-to-teacher assignments) into cache"""
        logger.info("Loading roster data (student-teacher assignments)...")
        page = 1

        while True:
            params = {'page': page, 'limit': 1000}
            data = self._make_api_request('/Api/Roster/', params)

            if not data or 'results' not in data:
                break

            results = data['results']
            if not results:
                break

            for record in results:
                district_student_id = record.get('district_student_id')
                if district_student_id:
                    # Store ALL sections for each student (not just first)
                    if str(district_student_id) not in self.roster_cache:
                        self.roster_cache[str(district_student_id)] = []

                    self.roster_cache[str(district_student_id)].append({
                        'user_id': str(record.get('user_id')),
                        'grade_level_id': record.get('grade_level_id'),
                        'section_id': str(record.get('section_id')),
                        'site_id': record.get('site_id'),
                        'course_id': record.get('course_id')
                    })

            logger.info(f"Loaded page {page} of roster, total cached: {len(self.roster_cache)}")

            if page >= data.get('num_pages', 1):
                break

            page += 1
            time.sleep(0.2)

        logger.info(f"Finished loading {len(self.roster_cache)} student-teacher assignments")

    def _load_lpc_roster_cache(self):
        """Load LPC_StudentRoster table from database into cache for teacher matching"""
        if not self.db_connection:
            logger.warning("Database not connected. Cannot load LPC roster cache.")
            return

        logger.info("Loading LPC_StudentRoster from database...")

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT
                    StudentID,
                    sectionID,
                    TeacherFirst,
                    TeacherLast,
                    SubjectArea,
                    GradeLevel,
                    ContentArea,
                    course_name
                FROM LPC_StudentRoster
            """)

            for row in cursor.fetchall():
                student_id = str(row[0])
                section_id = str(row[1])

                # Store by student ID - each student can have multiple sections
                if student_id not in self.lpc_roster_cache:
                    self.lpc_roster_cache[student_id] = []

                self.lpc_roster_cache[student_id].append({
                    'section_id': section_id,
                    'teacher_first': row[2],
                    'teacher_last': row[3],
                    'subject_area': row[4],  # 1=ELA, 2=Math, 3=Science, 4=Social Studies
                    'grade_level': row[5],
                    'content_area': row[6],
                    'course_name': row[7]
                })

            cursor.close()
            logger.info(f"Loaded LPC roster for {len(self.lpc_roster_cache)} students")

            # Build fast lookup index: (student_id, subject_area, content_area) -> section_info
            # This eliminates need to loop through sections for each assessment record
            logger.info("Building section lookup index for O(1) teacher matching...")
            index_count = 0
            for student_id, sections in self.lpc_roster_cache.items():
                for section in sections:
                    subject_area = section.get('subject_area')
                    content_area = section.get('content_area')

                    # Create lookup key: (student_id: str, subject_area: int, content_area: int)
                    # IMPORTANT: student_id is already str, subject_area and content_area are int from SQL
                    if subject_area is not None and content_area is not None:
                        key = (student_id, subject_area, content_area)
                        # Store first matching section (students shouldn't have duplicate SA+CA combos)
                        if key not in self.section_lookup_index:
                            self.section_lookup_index[key] = section
                            index_count += 1

            logger.info(f"Built section lookup index with {index_count} unique (student, subject, content) combinations")

        except Exception as e:
            logger.error(f"Error loading LPC_StudentRoster cache: {e}")

    def _load_subject_content_mapping(self):
        """
        Load Module_MonthAssignment from LessonPlanProduction database.
        Creates a mapping of Subject -> (SACode, List of valid ContentArea IDs).

        This determines which ContentArea values in LPC_StudentRoster are valid for each subject.
        For example: ELA -> SACode=1, ContentArea IN (1,2,3,4,28-36)
        """
        if not self.db_connection:
            logger.warning("Database not connected. Cannot load Module_MonthAssignment.")
            return

        logger.info("Loading Module_MonthAssignment from LessonPlan_Production database...")

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT DISTINCT
                    Subject_Area,
                    SACode,
                    courseIDCode
                FROM LessonPlan_Production.dbo.Module_MonthAssignment
                ORDER BY Subject_Area, SACode, courseIDCode
            """)

            for row in cursor.fetchall():
                subject_area = row[0]  # e.g., "English Language Arts", "Mathematics"
                sa_code = row[1]  # e.g., 1, 2, 3, 4
                course_id_code = row[2]  # e.g., 28, 34, etc.

                if subject_area not in self.subject_content_map:
                    self.subject_content_map[subject_area] = {
                        'sa_code': sa_code,
                        'content_areas': []
                    }

                # Add this ContentArea ID to the list of valid ones for this subject
                if course_id_code not in self.subject_content_map[subject_area]['content_areas']:
                    self.subject_content_map[subject_area]['content_areas'].append(course_id_code)

            cursor.close()

            # Log what we loaded
            for subject, data in self.subject_content_map.items():
                logger.info(f"  {subject}: SACode={data['sa_code']}, ContentAreas={len(data['content_areas'])} values")

            logger.info(f"Loaded {len(self.subject_content_map)} subject mappings from Module_MonthAssignment")

            # Pre-compute subject abbreviation mappings for fast O(1) lookup during extraction
            # Instead of doing this mapping 179,000 times, we do it once here
            logger.info("Pre-computing subject abbreviation mappings for fast lookup...")

            # Map common assessment subject abbreviations to their full names
            subject_name_to_key = {
                'ELA': 'English Language Arts',
                'English': 'English Language Arts',
                'Math': 'Mathematics',
                'Mathematics': 'Mathematics',
                'Science': 'Science',
                'Social Studies': 'Social Studies'
            }

            for subject_abbrev, subject_full in subject_name_to_key.items():
                if subject_full in self.subject_content_map:
                    # Store the SA code and list of valid ContentArea IDs for this subject
                    self.subject_sa_map[subject_abbrev] = {
                        'sa_code': self.subject_content_map[subject_full]['sa_code'],
                        'content_areas': self.subject_content_map[subject_full]['content_areas']
                    }

            logger.info(f"Pre-computed {len(self.subject_sa_map)} subject abbreviation mappings")

        except Exception as e:
            logger.error(f"Error loading Module_MonthAssignment: {e}")

    def connect_db(self):
        """Connect to SQL Server database"""
        try:
            # Build SQL Server connection string
            server = self.config.get('database', 'server')
            database = self.config.get('database', 'database')

            # Check if using Windows authentication or SQL authentication
            use_windows_auth = self.config.getboolean('database', 'windows_auth', fallback=False)

            if use_windows_auth:
                conn_string = (
                    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                    f'SERVER={server};'
                    f'DATABASE={database};'
                    f'Trusted_Connection=yes;'
                    f'Connection Timeout=30;'
                    f'Login Timeout=30;'
                    f'Mars_Connection=yes;'
                )
            else:
                username = self.config.get('database', 'username')
                password = self.config.get('database', 'password')
                conn_string = (
                    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                    f'SERVER={server};'
                    f'DATABASE={database};'
                    f'UID={username};'
                    f'PWD={password};'
                    f'Connection Timeout=30;'
                    f'Login Timeout=30;'
                    f'Mars_Connection=yes;'
                )

            self.db_connection = pyodbc.connect(conn_string)
            logger.info("Successfully connected to SQL Server database")
            return True
        except pyodbc.Error as e:
            logger.error(f"Error connecting to SQL Server database: {e}")
            return False

    def disconnect_db(self):
        """Disconnect from database"""
        if self.db_connection:
            self.db_connection.close()
            logger.info("Database connection closed")

    def _make_api_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make an authenticated API request"""
        # Remove leading slash from endpoint if present to avoid double slashes
        endpoint = endpoint.lstrip('/')
        url = f"{self.base_url}/{endpoint}"

        # Add consumer key to params as required by API
        if params is None:
            params = {}
        params['consumerKey'] = self.config.get('oauth', 'consumer_key')

        try:
            response = requests.get(url, auth=self.oauth, params=params, timeout=30)
            logger.info(f"Request URL: {url}")
            logger.info(f"Request Params: {params}")
            logger.info(f"Response Status: {response.status_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")
            logger.info(f"Response Text (first 500 chars): {response.text[:500]}")

            # If 401, log more details for debugging
            if response.status_code == 401:
                logger.error("Authentication failed - check OAuth credentials in config.ini")
                logger.error("Ensure Consumer Key, Consumer Secret, Access Token, and Access Token Secret are correct")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {endpoint}: {e}")
            logger.error(f"Response content: {response.text if 'response' in locals() else 'No response'}")
            return None

    def _log_extraction(self, endpoint: str, records_count: int, status: str, error_msg: str = None):
        """Log extraction attempt to database"""
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO api_extraction_log (endpoint, records_extracted, status, error_message)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (endpoint, records_count, status, error_msg))
            self.db_connection.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Failed to log extraction: {e}")

    def extract_assessments(self, school_ids: List[int] = None, page_size: int = 1000) -> int:
        """
        Extract all assessments from the API

        Args:
            school_ids: Optional list of school IDs to filter
            page_size: Number of records per page (max 1000)

        Returns:
            Total number of assessments extracted
        """
        logger.info("Starting assessment extraction...")
        total_extracted = 0
        page = 1

        try:
            while True:
                params = {
                    'page': page,
                    'per_page': page_size
                }

                if school_ids:
                    params['site_id'] = ','.join(map(str, school_ids))

                data = self._make_api_request('assessments', params)

                if not data or 'results' not in data:
                    break

                assessments = data['results']
                if not assessments:
                    break

                for assessment in assessments:
                    self._save_assessment(assessment)
                    total_extracted += 1

                logger.info(f"Processed page {page}, total assessments: {total_extracted}")

                # Check if there are more pages
                if page >= data.get('num_pages', 1):
                    break

                page += 1
                time.sleep(0.5)  # Rate limiting

            self._log_extraction('assessments', total_extracted, 'success')
            logger.info(f"Assessment extraction completed. Total: {total_extracted}")
            return total_extracted

        except Exception as e:
            logger.error(f"Error during assessment extraction: {e}")
            self._log_extraction('assessments', total_extracted, 'error', str(e))
            return total_extracted

    def _save_assessment(self, assessment: Dict):
        """Save assessment to database"""
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                INSERT INTO assessments (
                    assessment_id, local_assessment_id, title, description,
                    subject_id, subject_name, scope_id, scope_name,
                    author_id, author_name, version, created_date, modified_date, deleted
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    description = VALUES(description),
                    subject_name = VALUES(subject_name),
                    scope_name = VALUES(scope_name),
                    author_name = VALUES(author_name),
                    version = VALUES(version),
                    modified_date = VALUES(modified_date),
                    deleted = VALUES(deleted),
                    updated_at = CURRENT_TIMESTAMP
            """

            values = (
                assessment.get('assessment_id'),
                assessment.get('local_assessment_id'),
                assessment.get('title'),
                assessment.get('description'),
                assessment.get('subject_id'),
                assessment.get('subject_name'),
                assessment.get('scope_id'),
                assessment.get('scope_name'),
                assessment.get('author_id'),
                assessment.get('author_name'),
                assessment.get('version'),
                assessment.get('created_date'),
                assessment.get('modified_date'),
                assessment.get('deleted', False)
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except Error as e:
            logger.error(f"Failed to save assessment {assessment.get('assessment_id')}: {e}")

    def extract_assessment_details(self, assessment_id: int):
        """
        Extract detailed information about a specific assessment including questions and standards

        Args:
            assessment_id: The ID of the assessment to extract details for
        """
        logger.info(f"Extracting details for assessment {assessment_id}...")

        try:
            data = self._make_api_request(f'assessments/{assessment_id}')

            if not data:
                logger.warning(f"No data returned for assessment {assessment_id}")
                return

            # Save performance bands
            if 'performance_band_sets' in data:
                for band_set in data['performance_band_sets']:
                    for band in band_set.get('bands', []):
                        self._save_performance_band(assessment_id, band)

            # Save questions
            if 'questions' in data:
                for question in data['questions']:
                    question_id = self._save_question(assessment_id, question)

                    # Save answer choices
                    if question_id and 'answer_choices' in question:
                        for choice in question['answer_choices']:
                            self._save_answer_choice(question_id, choice)

                    # Save standards alignment
                    if question_id and 'standards' in question:
                        for standard in question['standards']:
                            standard_id = self._save_standard(standard)
                            if standard_id:
                                self._link_question_standard(question_id, standard_id)

            logger.info(f"Successfully extracted details for assessment {assessment_id}")

        except Exception as e:
            logger.error(f"Error extracting details for assessment {assessment_id}: {e}")

    def _save_performance_band(self, assessment_id: int, band: Dict):
        """Save performance band to database"""
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO performance_bands (assessment_id, band_name, min_score, max_score, color)
                VALUES (%s, %s, %s, %s, %s)
            """
            values = (
                assessment_id,
                band.get('name'),
                band.get('min_score'),
                band.get('max_score'),
                band.get('color')
            )
            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Failed to save performance band: {e}")

    def _save_question(self, assessment_id: int, question: Dict) -> Optional[int]:
        """Save question to database and return question_id"""
        if not self.db_connection:
            return None

        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO assessment_questions (
                    assessment_id, question_number, question_text,
                    question_type, max_points, correct_answer
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    question_text = VALUES(question_text),
                    question_type = VALUES(question_type),
                    max_points = VALUES(max_points),
                    correct_answer = VALUES(correct_answer)
            """
            values = (
                assessment_id,
                question.get('question_number'),
                question.get('question_text'),
                question.get('question_type'),
                question.get('max_points'),
                question.get('correct_answer')
            )
            cursor.execute(query, values)
            self.db_connection.commit()
            question_id = cursor.lastrowid
            cursor.close()
            return question_id
        except Error as e:
            logger.error(f"Failed to save question: {e}")
            return None

    def _save_answer_choice(self, question_id: int, choice: Dict):
        """Save answer choice to database"""
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO answer_choices (question_id, choice_letter, choice_text, is_correct)
                VALUES (%s, %s, %s, %s)
            """
            values = (
                question_id,
                choice.get('letter'),
                choice.get('text'),
                choice.get('is_correct', False)
            )
            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Failed to save answer choice: {e}")

    def _save_standard(self, standard: Dict) -> Optional[int]:
        """Save standard to database and return standard_id"""
        if not self.db_connection:
            return None

        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO standards (
                    standard_id, standard_code, standard_description,
                    subject, grade_level
                )
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    standard_description = VALUES(standard_description),
                    subject = VALUES(subject),
                    grade_level = VALUES(grade_level)
            """
            values = (
                standard.get('standard_id'),
                standard.get('code'),
                standard.get('description'),
                standard.get('subject'),
                standard.get('grade_level')
            )
            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()
            return standard.get('standard_id')
        except Error as e:
            logger.error(f"Failed to save standard: {e}")
            return None

    def _link_question_standard(self, question_id: int, standard_id: int):
        """Link question to standard"""
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT IGNORE INTO question_standards (question_id, standard_id)
                VALUES (%s, %s)
            """
            cursor.execute(query, (question_id, standard_id))
            self.db_connection.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Failed to link question to standard: {e}")

    def extract_student_scores(self, assessment_id: int = None,
                               start_date: str = None,
                               end_date: str = None,
                               school_ids: List[int] = None) -> int:
        """
        Extract student assessment scores

        Args:
            assessment_id: Optional specific assessment ID
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            school_ids: Optional list of school IDs

        Returns:
            Total number of scores extracted
        """
        logger.info("Starting student scores extraction...")
        total_extracted = 0
        page = 1

        try:
            while True:
                params = {
                    'page': page,
                    'per_page': 1000
                }

                if assessment_id:
                    params['assessment_id'] = assessment_id
                if start_date:
                    params['start_date'] = start_date
                if end_date:
                    params['end_date'] = end_date
                if school_ids:
                    params['site_id'] = ','.join(map(str, school_ids))

                data = self._make_api_request('students/assessments', params)

                if not data or 'results' not in data:
                    break

                scores = data['results']
                if not scores:
                    break

                for score in scores:
                    self._save_student_score(score)
                    total_extracted += 1

                logger.info(f"Processed page {page}, total scores: {total_extracted}")

                if page >= data.get('num_pages', 1):
                    break

                page += 1
                time.sleep(0.5)

            self._log_extraction('student_scores', total_extracted, 'success')
            logger.info(f"Student scores extraction completed. Total: {total_extracted}")
            return total_extracted

        except Exception as e:
            logger.error(f"Error during student scores extraction: {e}")
            self._log_extraction('student_scores', total_extracted, 'error', str(e))
            return total_extracted

    def _save_student_score(self, score: Dict):
        """Save student score to database"""
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                INSERT INTO student_scores (
                    student_id, assessment_id, local_student_id,
                    test_date, raw_score, percent_correct,
                    performance_band, version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    raw_score = VALUES(raw_score),
                    percent_correct = VALUES(percent_correct),
                    performance_band = VALUES(performance_band),
                    version = VALUES(version),
                    updated_at = CURRENT_TIMESTAMP
            """

            values = (
                score.get('student_id'),
                score.get('assessment_id'),
                score.get('local_student_id'),
                score.get('test_date'),
                score.get('raw_score'),
                score.get('percent_correct'),
                score.get('performance_band'),
                score.get('version')
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except Error as e:
            logger.error(f"Failed to save student score: {e}")

    def extract_all_data(self, school_ids: List[int] = None):
        """
        Main method to extract all data

        Args:
            school_ids: Optional list of school IDs to filter
        """
        logger.info("=" * 60)
        logger.info("Starting full data extraction from Illuminate API")
        logger.info("=" * 60)

        if not self.connect_db():
            logger.error("Cannot proceed without database connection")
            return

        try:
            # Extract assessments
            assessment_count = self.extract_assessments(school_ids=school_ids)
            logger.info(f"Extracted {assessment_count} assessments")

            # Extract student scores
            score_count = self.extract_student_scores(school_ids=school_ids)
            logger.info(f"Extracted {score_count} student scores")

            logger.info("=" * 60)
            logger.info("Data extraction completed successfully")
            logger.info("=" * 60)

        finally:
            self.disconnect_db()

    # ========== ILLUMINATE DATA EXTRACTION METHODS ==========
    # These methods extract ALL Illuminate assessment data to Illuminate_* tables
    # Then HMH data can be filtered/synced to HMH_* tables using sp_Sync_HMH_Data

    def _match_section_for_assessment(self, student_id: str, subject: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        OPTIMIZED: Fast O(1) lookup using pre-built section_lookup_index.

        Find the correct section for a student based on assessment subject.
        Uses pre-computed subject_sa_map to get SACode and valid ContentArea IDs,
        then does O(1) hash lookup instead of looping through sections.

        Subject mapping (pre-computed from Module_MonthAssignment):
        - 'ELA' or 'English' -> SACode=1, ContentArea IN (1,2,3,4,28-36)
        - 'Math' or 'Mathematics' -> SACode=2, ContentArea IN (34,...)
        - 'Science' -> SACode=3
        - 'Social Studies' -> SACode=4

        This ensures we match "Common Core ELA" (ContentArea=28) but NOT "Reading Foundations" (ContentArea=37).

        Returns:
            Tuple of (section_id, section_info_dict) or (None, None) if not found
        """
        if not subject:
            return (None, None)

        # Use pre-computed subject mapping (already done at startup)
        subject_data = self.subject_sa_map.get(subject)
        if not subject_data:
            logger.debug(f"Unknown subject '{subject}', cannot match section")
            return (None, None)

        target_sa_code = subject_data['sa_code']  # int
        valid_content_areas = subject_data['content_areas']  # list of int

        # Try each valid ContentArea with O(1) hash lookup
        # Key format: (student_id: str, subject_area: int, content_area: int)
        # IMPORTANT: This must match the key format used when building the index (line 275)
        for content_area in valid_content_areas:
            key = (str(student_id), target_sa_code, content_area)
            section = self.section_lookup_index.get(key)

            if section:
                course_name = section.get('course_name', 'N/A')
                logger.debug(f"✓ Fast lookup matched section: SubjectArea={target_sa_code}, ContentArea={content_area}, Course='{course_name}'")
                return (section.get('section_id'), section)

        # If no match found
        logger.debug(f"✗ No matching section found for student {student_id}, subject '{subject}'")
        return (None, None)

    def _truncate_illuminate_tables(self):
        """
        Truncate Illuminate_Assessment_Results table for fresh extraction.
        This removes all existing data before inserting new data.
        """
        if not self.db_connection:
            logger.error("Database not connected. Cannot truncate tables.")
            return

        try:
            cursor = self.db_connection.cursor()

            logger.info("Truncating Illuminate_Assessment_Results...")
            cursor.execute("TRUNCATE TABLE Illuminate_Assessment_Results")

            self.db_connection.commit()
            cursor.close()

            logger.info("✓ Table truncated successfully - ready for fresh data")

        except Exception as e:
            logger.error(f"Error truncating tables: {e}")
            raise

    def extract_illuminate_assessment_data(self,
                                           school_ids: List[int] = None,
                                           start_date: str = None,
                                           end_date: str = None,
                                           academic_year: str = None) -> int:
        """
        Extract ALL Illuminate assessment data (not just HMH) with standards-based scoring.

        This is the main extraction method that saves all data to Illuminate_* tables.
        After extraction, run sp_Sync_HMH_Data to populate HMH_* tables with filtered data.

        This function tries multiple potential endpoints:
        1. students/assessment_standards - Standards-based assessment data
        2. students/assessments - Standard assessment results

        Args:
            school_ids: Optional list of school IDs to filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            academic_year: Academic year (e.g., '2024-2025')

        Returns:
            Total number of assessment records extracted
        """
        logger.info("=" * 60)
        logger.info("Starting Illuminate assessment data extraction")
        logger.info("=" * 60)

        if not self.connect_db():
            logger.error("Cannot proceed without database connection")
            return 0

        total_extracted = 0

        try:
            # Test API connection
            logger.info("Testing API connection with /Api/Sites endpoint...")
            test_data = self._make_api_request('/Api/Sites')
            if test_data:
                logger.info(f"API connection successful! Found {len(test_data)} sites")
            else:
                logger.error("API connection failed!")
                return 0

            # Load reference data into cache for school names, teachers, and roster
            logger.info("\n" + "=" * 60)
            logger.info("Loading reference data (sites, students, teachers, and roster)...")
            logger.info("=" * 60)
            self._load_sites_cache()
            self._load_students_cache()
            self._load_users_cache()
            self._load_roster_cache()
            self._load_lpc_roster_cache()  # Load LPC roster for teacher matching
            self._load_subject_content_mapping()  # Load Module_MonthAssignment for ContentArea matching

            # Truncate tables before fresh extraction
            logger.info("\n" + "=" * 60)
            logger.info("Truncating Illuminate_Assessment_Results table for fresh extraction...")
            logger.info("=" * 60)
            self._truncate_illuminate_tables()

            # Extract from the correct standards-based endpoint
            logger.info("\n" + "=" * 60)
            logger.info("Starting extraction from /Api/AssessmentAggregateStudentResponsesStandard/")
            logger.info("=" * 60)
            count = self._extract_from_standards_api(
                school_ids, start_date, end_date, academic_year
            )
            total_extracted += count
            logger.info(f"Extracted {count} standards-based assessment records")

            logger.info("=" * 60)
            logger.info(f"Illuminate extraction completed. Total records: {total_extracted}")
            logger.info("=" * 60)

            return total_extracted

        except Exception as e:
            logger.error(f"Error during Illuminate extraction: {e}")
            return total_extracted
        finally:
            self.disconnect_db()

    def _extract_from_standards_api(self,
                                    school_ids: List[int] = None,
                                    start_date: str = None,
                                    end_date: str = None,
                                    academic_year: str = None) -> int:
        """
        Extract ALL assessment data from /Api/AssessmentAggregateStudentResponsesStandard/
        This is the CORRECT endpoint per Illuminate API documentation.
        Table is truncated at start, then all records are freshly inserted.
        """
        total_extracted = 0
        total_skipped = 0
        page = 1

        while True:
            params = {
                'page': page,
                'limit': 1000  # API docs say use 'limit' not 'per_page'
            }

            if school_ids:
                params['site_id'] = ','.join(map(str, school_ids))
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            data = self._make_api_request('/Api/AssessmentAggregateStudentResponsesStandard/', params)

            if not data or 'results' not in data:
                break

            results = data['results']
            if not results:
                break

            # Create ONE cursor for the entire page
            cursor = self.db_connection.cursor()

            # TIMING: Measure time spent preparing values (includes teacher matching)
            import time as time_module
            prepare_start = time_module.time()

            # Prepare all INSERT values for batch insert (collect values, don't execute yet)
            values_list = []
            for result in results:
                # Prepare values tuple (returns None if skipped)
                values = self._prepare_illuminate_standards_values(result, academic_year)
                if values:
                    values_list.append(values)
                else:
                    total_skipped += 1

            prepare_time = time_module.time() - prepare_start

            # TIMING: Measure time spent on batch INSERT
            insert_start = time_module.time()

            # Batch INSERT all records with ONE database call
            if values_list:
                query = """
                    INSERT INTO Illuminate_Assessment_Results (
                        AcademicYear, DistrictName, SchoolName,
                        StudentID_SASID, StudentID_LASID,
                        LastName, FirstName, StudentGrade,
                        ClassName, TeacherLastName, TeacherFirstName, ClassGrade,
                        Subject, ProgramName, Publisher, Component, AssignmentName,
                        AssessmentID, DateCompleted, StandardSet, StandardCodingNumber, StandardDescription,
                        PointsAchieved, PointsPossible, PercentCorrect, SchoolID, SectionID
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                cursor.executemany(query, values_list)
                total_extracted += len(values_list)

            insert_time = time_module.time() - insert_start

            cursor.close()

            # TIMING: Measure time spent on commit
            commit_start = time_module.time()

            # Batch commit after each page for performance
            self.db_connection.commit()

            commit_time = time_module.time() - commit_start

            # Log progress every page WITH TIMING BREAKDOWN
            num_pages = data.get('num_pages', 1)
            logger.info(f"Processed page {page}/{num_pages}, inserted: {total_extracted}, skipped: {total_skipped}")
            logger.info(f"  ⏱️  Timing breakdown: Prepare={prepare_time:.2f}s, INSERT={insert_time:.2f}s, COMMIT={commit_time:.2f}s, Total={prepare_time+insert_time+commit_time:.2f}s")

            if page >= num_pages:
                break

            page += 1
            time.sleep(0.3)  # Rate limiting (reduced for faster extraction)

        # Log final summary
        logger.info(f"Extraction complete - Total records inserted: {total_extracted}")
        if total_skipped > 0:
            logger.info(f"  - Records skipped (no SchoolID): {total_skipped}")

        return total_extracted

    def _prepare_illuminate_standards_values(self, result: Dict, academic_year: str = None):
        """
        Prepare values tuple for a single standards-based result from /Api/AssessmentAggregateStudentResponsesStandard/
        to be inserted into Illuminate_Assessment_Results table using executemany().

        Table is truncated before extraction starts, so all records are new inserts.

        Args:
            result: Assessment result data from API
            academic_year: Optional academic year override

        Returns:
            Tuple of values ready for INSERT, or None if record should be skipped
        """
        try:
            # Determine academic year if not provided
            if not academic_year:
                academic_year = self._determine_academic_year(result.get('date_taken'))

            # Enrich with student/school data from cache
            local_student_id = result.get('local_student_id')
            student_data = self.students_cache.get(str(local_student_id), {})
            state_student_id = student_data.get('state_student_id')
            student_grade = student_data.get('grade_level')
            site_id = student_data.get('site_id')
            school_name = student_data.get('site_name')  # From Enrollment API
            district_name = student_data.get('district_name')

            # Fallback to Sites cache if needed
            if not school_name and site_id:
                site_data = self.sites_cache.get(str(site_id), {})
                school_name = site_data.get('site_name')

            # Skip records without a SchoolID - can't determine which school they belong to
            if not site_id:
                logger.debug(f"Skipping record for student {local_student_id} - no SchoolID found")
                return None

            # Extract Subject from StandardCodingNumber FIRST (needed for teacher matching)
            # Examples: "ELA-Literacy.RL.3.5" -> "ELA", "Math.1.OA.1" -> "Math"
            standard_code = result.get('standard_code', '')
            subject = None
            if standard_code:
                if standard_code.startswith('ELA') or 'ELA-' in standard_code or '.ELA.' in standard_code:
                    subject = 'ELA'
                elif standard_code.startswith('Math') or 'Math.' in standard_code or '.Math.' in standard_code:
                    subject = 'Math'
                elif 'CCSS.ELA' in standard_code:
                    subject = 'ELA'
                elif 'CCSS.Math' in standard_code:
                    subject = 'Math'

            # Fallback: Extract subject from AssignmentName if StandardCodingNumber didn't provide it
            assignment_name = result.get('title', '')
            if not subject and assignment_name:
                assignment_lower = assignment_name.lower()

                # Check for Science
                if 'science' in assignment_lower or 'sci' in assignment_lower:
                    subject = 'Science'
                # Check for Social Studies (SS, Social, History)
                elif assignment_name.upper().startswith('SS') or 'social' in assignment_lower or 'history' in assignment_lower:
                    subject = 'Social Studies'
                # Check for ELA
                elif 'ela' in assignment_lower or 'english' in assignment_lower or 'reading' in assignment_lower:
                    subject = 'ELA'
                # Check for Math
                elif 'math' in assignment_lower:
                    subject = 'Math'

            # Match section based on assessment subject using LPC_StudentRoster
            section_id, section_info = self._match_section_for_assessment(local_student_id, subject)

            if section_info:
                # Use teacher from matched LPC section
                teacher_first_name = section_info.get('teacher_first')
                teacher_last_name = section_info.get('teacher_last')
            else:
                # Fallback to first roster entry from Illuminate API if no LPC match
                roster_entries = self.roster_cache.get(str(local_student_id), [])
                if roster_entries:
                    roster_info = roster_entries[0] if isinstance(roster_entries, list) else roster_entries
                    section_id = roster_info.get('section_id')
                    teacher_id = roster_info.get('user_id')
                    teacher_info = self.users_cache.get(str(teacher_id), {}) if teacher_id else {}
                    teacher_first_name = teacher_info.get('first_name')
                    teacher_last_name = teacher_info.get('last_name')
                else:
                    section_id = None
                    teacher_first_name = None
                    teacher_last_name = None

            # Use grade level from roster if not in student enrollment
            roster_entries = self.roster_cache.get(str(local_student_id), [])
            if not student_grade and roster_entries:
                roster_info = roster_entries[0] if isinstance(roster_entries, list) else roster_entries
                if roster_info.get('grade_level_id'):
                    # Convert grade_level_id to actual grade
                    student_grade = self._convert_grade_level_id(roster_info.get('grade_level_id'))

            # Infer StandardSet from StandardCodingNumber prefix
            # CCSS.* = Common Core State Standards (NGA/CCSSO)
            # ELA-Literacy.* or Math.Content.* (no CCSS) = Michigan State Standards
            standard_set = None
            if standard_code:
                if standard_code.startswith('CCSS.'):
                    standard_set = 'Common Core State Standards'
                elif standard_code.startswith('ELA-Literacy.') or standard_code.startswith('Math.Content.'):
                    standard_set = 'Michigan State Standards'
                # Try from API first (may be provided)
                if not standard_set and result.get('standard_set'):
                    standard_set = result.get('standard_set')

            # Return values tuple for batch INSERT with executemany()
            return (
                academic_year,
                district_name,  # Enriched from cache
                school_name,  # Enriched from cache
                state_student_id,  # Enriched from cache
                local_student_id,
                result.get('last_name'),
                result.get('first_name'),
                student_grade,  # Enriched from cache
                None,  # Class name not in response
                teacher_last_name,  # Enriched from LPC roster or fallback
                teacher_first_name,  # Enriched from LPC roster or fallback
                None,  # Class grade not in response
                subject,  # Extracted from StandardCodingNumber
                None,  # Program name not in response
                None,  # Publisher not in response
                None,  # Component not in response
                result.get('title'),  # Assignment name = assessment title
                result.get('assessment_id'),
                self._parse_date(result.get('date_taken')),
                standard_set,  # Inferred from standard code prefix
                result.get('standard_code'),
                result.get('standard_description'),
                self._safe_decimal(result.get('points')),
                self._safe_decimal(result.get('points_possible')),
                self._calculate_percent(result.get('points'), result.get('points_possible')),
                site_id,  # Enriched from cache
                section_id  # Added SectionID from LPC roster match
            )

        except Exception as e:
            logger.error(f"Failed to prepare Illuminate standards values: {e}")
            logger.error(f"Result data: {json.dumps(result, indent=2)}")
            return None  # Skip this record

    def _extract_illuminate_from_standards_endpoint(self,
                                                    school_ids: List[int] = None,
                                                    start_date: str = None,
                                                    end_date: str = None,
                                                    academic_year: str = None) -> int:
        """
        Extract ALL assessment data from students/assessment_standards endpoint.
        This endpoint typically provides standards-level performance data.
        """
        total_extracted = 0
        page = 1

        while True:
            params = {
                'page': page,
                'per_page': 1000
            }

            if school_ids:
                params['site_id'] = ','.join(map(str, school_ids))
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            data = self._make_api_request('students/assessment_standards', params)

            if not data or 'results' not in data:
                break

            results = data['results']
            if not results:
                break

            for result in results:
                # Save ALL results (not filtered by HMH)
                self._process_illuminate_assessment_result(result, academic_year)
                total_extracted += 1

            logger.info(f"Processed page {page}, total records: {total_extracted}")

            if page >= data.get('num_pages', 1):
                break

            page += 1
            time.sleep(0.5)  # Rate limiting

        return total_extracted

    def _extract_illuminate_from_assessments_endpoint(self,
                                                      school_ids: List[int] = None,
                                                      start_date: str = None,
                                                      end_date: str = None,
                                                      academic_year: str = None) -> int:
        """
        Extract ALL assessment data from students/assessments endpoint.
        This is the standard assessment results endpoint.
        """
        total_extracted = 0
        page = 1

        while True:
            params = {
                'page': page,
                'per_page': 1000
            }

            if school_ids:
                params['site_id'] = ','.join(map(str, school_ids))
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            data = self._make_api_request('students/assessments', params)

            if not data or 'results' not in data:
                break

            results = data['results']
            if not results:
                break

            for result in results:
                # Save ALL results (not filtered by HMH)
                self._process_illuminate_assessment_result(result, academic_year)
                total_extracted += 1

            logger.info(f"Processed page {page}, total records: {total_extracted}")

            if page >= data.get('num_pages', 1):
                break

            page += 1
            time.sleep(0.5)

        return total_extracted

    def _process_illuminate_assessment_result(self, result: Dict, academic_year: str = None):
        """
        Process a single Illuminate assessment result and store in Illuminate_* tables.

        This saves ALL assessment data (HMH and non-HMH).
        HMH filtering happens later via sp_Sync_HMH_Data stored procedure.

        This function:
        1. Extracts overall assignment data for Illuminate_Assessment_Summary
        2. Extracts standards-level data for Illuminate_Assessment_Results
        3. Populates lookup tables (Illuminate_Standards, Illuminate_Assignments)
        """
        if not self.db_connection:
            return

        try:
            # Determine academic year if not provided
            if not academic_year:
                academic_year = self._determine_academic_year(
                    result.get('date_completed') or result.get('test_date')
                )

            # Extract common fields
            common_data = self._extract_common_illuminate_fields(result, academic_year)

            # Check if this result includes standards breakdown
            standards_data = result.get('standards', []) or result.get('standard_results', [])

            if standards_data:
                # Process standards-level data
                for standard in standards_data:
                    self._save_illuminate_assessment_result(common_data, standard)
                    self._save_illuminate_standard(standard, common_data.get('Subject'))

            # Save overall summary (if available)
            if result.get('overall_score') or result.get('points_achieved'):
                self._save_illuminate_assessment_summary(common_data, result)

            # Save assignment to lookup table
            self._save_illuminate_assignment(common_data)

        except Exception as e:
            logger.error(f"Error processing Illuminate assessment result: {e}")
            logger.error(f"Result data: {json.dumps(result, indent=2)}")

    def _extract_common_illuminate_fields(self, result: Dict, academic_year: str) -> Dict:
        """
        Extract common fields used across Illuminate tables from API result.

        Returns a dictionary with standardized field names matching the Illuminate schema.
        """
        return {
            'AcademicYear': academic_year,
            'DistrictName': result.get('district_name'),
            'SchoolName': result.get('school_name') or result.get('site_name'),
            'StudentID_SASID': result.get('state_student_id') or result.get('sasid'),
            'StudentID_LASID': result.get('local_student_id') or result.get('lasid') or result.get('student_id'),
            'LastName': result.get('last_name') or result.get('student_last_name'),
            'FirstName': result.get('first_name') or result.get('student_first_name'),
            'StudentGrade': result.get('grade_level') or result.get('student_grade'),
            'ClassName': result.get('class_name') or result.get('section_name'),
            'TeacherLastName': result.get('teacher_last_name'),
            'TeacherFirstName': result.get('teacher_first_name'),
            'ClassGrade': result.get('class_grade_level') or result.get('grade_level'),
            'Subject': result.get('subject') or result.get('subject_name'),
            'ProgramName': result.get('program_name'),
            'Publisher': result.get('publisher'),
            'Component': result.get('component'),
            'AssignmentName': result.get('assessment_name') or result.get('assessment_title') or result.get('assignment_name'),
            'AssessmentID': result.get('assessment_id'),
            'DateCompleted': self._parse_date(result.get('date_completed') or result.get('test_date')),
            'SchoolID': result.get('school_id') or result.get('site_id'),
        }

    def _save_illuminate_assessment_result(self, common_data: Dict, standard: Dict):
        """
        Save a single standards-based assessment result to Illuminate_Assessment_Results table.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                INSERT INTO Illuminate_Assessment_Results (
                    AcademicYear, DistrictName, SchoolName,
                    StudentID_SASID, StudentID_LASID,
                    LastName, FirstName, StudentGrade,
                    ClassName, TeacherLastName, TeacherFirstName, ClassGrade,
                    Subject, ProgramName, Publisher, Component, AssignmentName,
                    AssessmentID, DateCompleted, StandardSet, StandardCodingNumber, StandardDescription,
                    PointsAchieved, PointsPossible, PercentCorrect, SchoolID
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            values = (
                common_data.get('AcademicYear'),
                common_data.get('DistrictName'),
                common_data.get('SchoolName'),
                common_data.get('StudentID_SASID'),
                common_data.get('StudentID_LASID'),
                common_data.get('LastName'),
                common_data.get('FirstName'),
                common_data.get('StudentGrade'),
                common_data.get('ClassName'),
                common_data.get('TeacherLastName'),
                common_data.get('TeacherFirstName'),
                common_data.get('ClassGrade'),
                common_data.get('Subject'),
                common_data.get('ProgramName'),
                common_data.get('Publisher'),
                common_data.get('Component'),
                common_data.get('AssignmentName'),
                common_data.get('AssessmentID'),
                common_data.get('DateCompleted'),
                standard.get('standard_set') or standard.get('set_name'),
                standard.get('standard_code') or standard.get('code'),
                standard.get('standard_description') or standard.get('description'),
                self._safe_decimal(standard.get('points_achieved') or standard.get('score')),
                self._safe_decimal(standard.get('points_possible') or standard.get('max_score')),
                self._calculate_percent(
                    standard.get('points_achieved') or standard.get('score'),
                    standard.get('points_possible') or standard.get('max_score')
                ),
                common_data.get('SchoolID')
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save Illuminate assessment result: {e}")

    def _save_illuminate_assessment_summary(self, common_data: Dict, result: Dict):
        """
        Save overall assessment summary to Illuminate_Assessment_Summary table.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            total_achieved = self._safe_decimal(
                result.get('points_achieved') or
                result.get('total_score') or
                result.get('raw_score')
            )
            total_possible = self._safe_decimal(
                result.get('points_possible') or
                result.get('max_score')
            )

            values = (
                common_data.get('AcademicYear'),
                common_data.get('SchoolName'),
                common_data.get('StudentID_SASID'),
                common_data.get('StudentID_LASID'),
                common_data.get('LastName'),
                common_data.get('FirstName'),
                common_data.get('StudentGrade'),
                common_data.get('ClassName'),
                common_data.get('TeacherLastName'),
                common_data.get('TeacherFirstName'),
                common_data.get('Subject'),
                common_data.get('ProgramName'),
                common_data.get('Publisher'),
                common_data.get('Component'),
                common_data.get('AssignmentName'),
                common_data.get('AssessmentID'),
                common_data.get('DateCompleted'),
                result.get('standard_set'),
                total_achieved,
                total_possible,
                self._calculate_percent(total_achieved, total_possible),
                common_data.get('SchoolID')
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save Illuminate assessment summary: {e}")

    def _save_illuminate_standard(self, standard: Dict, subject: str = None):
        """
        Save standard to Illuminate_Standards lookup table.
        Uses MERGE to avoid duplicates.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                MERGE Illuminate_Standards AS target
                USING (SELECT ? AS StandardSet, ? AS StandardCodingNumber) AS source
                ON (target.StandardSet = source.StandardSet AND target.StandardCodingNumber = source.StandardCodingNumber)
                WHEN NOT MATCHED THEN
                    INSERT (StandardSet, StandardCodingNumber, StandardDescription, Subject)
                    VALUES (?, ?, ?, ?);
            """

            standard_set = standard.get('standard_set') or standard.get('set_name')
            standard_code = standard.get('standard_code') or standard.get('code')
            standard_desc = standard.get('standard_description') or standard.get('description')

            values = (
                standard_set, standard_code,  # For the USING clause
                standard_set, standard_code, standard_desc, subject  # For the INSERT
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save Illuminate standard: {e}")

    def _save_illuminate_assignment(self, common_data: Dict):
        """
        Save assignment to Illuminate_Assignments lookup table.
        Uses MERGE to avoid duplicates.
        Includes SchoolID to allow same assessment name at different schools.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                MERGE Illuminate_Assignments AS target
                USING (SELECT ? AS ProgramName, ? AS Component, ? AS AssignmentName, ? AS SchoolID) AS source
                ON (target.ProgramName = source.ProgramName
                    AND target.Component = source.Component
                    AND target.AssignmentName = source.AssignmentName
                    AND target.SchoolID = source.SchoolID)
                WHEN NOT MATCHED THEN
                    INSERT (ProgramName, Publisher, Component, AssignmentName, IlluminateAssessmentID, Subject, SchoolID)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
            """

            program = common_data.get('ProgramName')
            publisher = common_data.get('Publisher')
            component = common_data.get('Component')
            assignment = common_data.get('AssignmentName')
            assessment_id = common_data.get('AssessmentID')
            subject = common_data.get('Subject')
            school_id = common_data.get('SchoolID')

            values = (
                program, component, assignment, school_id,  # For the USING clause
                program, publisher, component, assignment, assessment_id, subject, school_id  # For the INSERT
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save Illuminate assignment: {e}")

    def _sync_hmh_data(self):
        """
        Run the sp_Sync_HMH_Data stored procedure to filter HMH data
        from Illuminate tables into HMH tables.
        """
        if not self.db_connection:
            return

        try:
            logger.info("Running sp_Sync_HMH_Data stored procedure...")
            cursor = self.db_connection.cursor()
            cursor.execute("EXEC sp_Sync_HMH_Data")

            # Get the results
            results = cursor.fetchone()
            if results:
                logger.info(f"Sync Status: {results[0]}")
                logger.info(f"HMH Results: {results[1]}, Summary: {results[2]}, Standards: {results[3]}, Assignments: {results[4]}")

            cursor.close()
            logger.info("HMH data sync completed successfully")

        except pyodbc.Error as e:
            logger.error(f"Failed to sync HMH data: {e}")

    # ========== HMH-SPECIFIC EXTRACTION METHODS (DEPRECATED) ==========
    # These methods are kept for backwards compatibility but the new approach is:
    # 1. Use extract_illuminate_assessment_data() to get ALL data into Illuminate_* tables
    # 2. Run sp_Sync_HMH_Data to filter HMH data into HMH_* tables

    def discover_api_endpoints(self):
        """
        Discovery function to explore available API endpoints and log their structures.
        Useful for identifying the correct endpoints for HMH assessment data.
        """
        logger.info("=" * 60)
        logger.info("Starting API endpoint discovery")
        logger.info("=" * 60)

        # List of potential endpoints to explore
        endpoints_to_try = [
            ('students/assessments', {'per_page': 1}),
            ('students/assessment_standards', {'per_page': 1}),
            ('reports/assessment_results', {'per_page': 1}),
            ('assessments/results', {'per_page': 1}),
            ('students/scores', {'per_page': 1}),
            ('students/standards_scores', {'per_page': 1}),
        ]

        for endpoint, params in endpoints_to_try:
            logger.info(f"\n--- Testing endpoint: {endpoint} ---")
            try:
                data = self._make_api_request(endpoint, params)
                if data:
                    logger.info(f"SUCCESS: {endpoint} returned data")
                    logger.info(f"Response structure: {json.dumps(data, indent=2)}")

                    # Save to file for review
                    with open(f'api_discovery_{endpoint.replace("/", "_")}.json', 'w') as f:
                        json.dump(data, f, indent=2)
                    logger.info(f"Saved response to api_discovery_{endpoint.replace('/', '_')}.json")
                else:
                    logger.warning(f"FAILED: {endpoint} returned no data")
            except Exception as e:
                logger.error(f"ERROR testing {endpoint}: {e}")

        logger.info("=" * 60)
        logger.info("API endpoint discovery completed")
        logger.info("=" * 60)

    def extract_hmh_assessment_data(self,
                                    school_ids: List[int] = None,
                                    start_date: str = None,
                                    end_date: str = None,
                                    academic_year: str = None) -> int:
        """
        Extract HMH assessment data with standards-based scoring.

        This function tries multiple potential endpoints to find HMH assessment data:
        1. students/assessment_standards - Most likely for standards-based data
        2. students/assessments - Standard assessment results
        3. reports/assessment_results - Comprehensive reports

        Args:
            school_ids: Optional list of school IDs to filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            academic_year: Academic year (e.g., '2024-2025')

        Returns:
            Total number of assessment records extracted
        """
        logger.info("=" * 60)
        logger.info("Starting HMH assessment data extraction")
        logger.info("=" * 60)

        if not self.connect_db():
            logger.error("Cannot proceed without database connection")
            return 0

        total_extracted = 0

        try:
            # Try primary endpoint for standards-based assessment data
            logger.info("Attempting to extract from students/assessment_standards endpoint...")
            count = self._extract_hmh_from_standards_endpoint(
                school_ids, start_date, end_date, academic_year
            )
            total_extracted += count

            if count == 0:
                logger.info("No data from standards endpoint, trying students/assessments...")
                count = self._extract_hmh_from_assessments_endpoint(
                    school_ids, start_date, end_date, academic_year
                )
                total_extracted += count

            logger.info("=" * 60)
            logger.info(f"HMH extraction completed. Total records: {total_extracted}")
            logger.info("=" * 60)

            return total_extracted

        except Exception as e:
            logger.error(f"Error during HMH extraction: {e}")
            return total_extracted
        finally:
            self.disconnect_db()

    def _extract_hmh_from_standards_endpoint(self,
                                             school_ids: List[int] = None,
                                             start_date: str = None,
                                             end_date: str = None,
                                             academic_year: str = None) -> int:
        """
        Extract HMH data from students/assessment_standards endpoint.
        This endpoint typically provides standards-level performance data.
        """
        total_extracted = 0
        page = 1

        while True:
            params = {
                'page': page,
                'per_page': 1000
            }

            if school_ids:
                params['site_id'] = ','.join(map(str, school_ids))
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            data = self._make_api_request('students/assessment_standards', params)

            if not data or 'results' not in data:
                break

            results = data['results']
            if not results:
                break

            for result in results:
                # Check if this is HMH assessment data
                if self._is_hmh_assessment(result):
                    self._process_hmh_assessment_result(result, academic_year)
                    total_extracted += 1

            logger.info(f"Processed page {page}, total HMH records: {total_extracted}")

            if page >= data.get('num_pages', 1):
                break

            page += 1
            time.sleep(0.5)  # Rate limiting

        return total_extracted

    def _extract_hmh_from_assessments_endpoint(self,
                                               school_ids: List[int] = None,
                                               start_date: str = None,
                                               end_date: str = None,
                                               academic_year: str = None) -> int:
        """
        Extract HMH data from students/assessments endpoint.
        This is the standard assessment results endpoint.
        """
        total_extracted = 0
        page = 1

        while True:
            params = {
                'page': page,
                'per_page': 1000
            }

            if school_ids:
                params['site_id'] = ','.join(map(str, school_ids))
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            data = self._make_api_request('students/assessments', params)

            if not data or 'results' not in data:
                break

            results = data['results']
            if not results:
                break

            for result in results:
                # Check if this is HMH assessment data
                if self._is_hmh_assessment(result):
                    self._process_hmh_assessment_result(result, academic_year)
                    total_extracted += 1

            logger.info(f"Processed page {page}, total HMH records: {total_extracted}")

            if page >= data.get('num_pages', 1):
                break

            page += 1
            time.sleep(0.5)

        return total_extracted

    def _is_hmh_assessment(self, result: Dict) -> bool:
        """
        Determine if an assessment result is from HMH.

        Checks for indicators like:
        - Program name contains 'HMH', 'Into Literature', 'Into Math', 'Into Reading'
        - Assessment title contains HMH identifiers
        - Component or subject indicates HMH source
        """
        hmh_identifiers = [
            'hmh', 'into literature', 'into math', 'into reading',
            'houghton mifflin', 'harcourt'
        ]

        # Check various fields (convert to lowercase for comparison)
        fields_to_check = [
            result.get('program_name', ''),
            result.get('assessment_title', ''),
            result.get('assessment_name', ''),
            result.get('component', ''),
            result.get('publisher', ''),
        ]

        for field in fields_to_check:
            field_lower = str(field).lower()
            for identifier in hmh_identifiers:
                if identifier in field_lower:
                    return True

        return False

    def _process_hmh_assessment_result(self, result: Dict, academic_year: str = None):
        """
        Process a single HMH assessment result and store in database.

        This function:
        1. Extracts overall assignment data for HMH_Assessment_Summary
        2. Extracts standards-level data for HMH_Assessment_Results
        3. Populates lookup tables (HMH_Standards, HMH_Assignments)
        """
        if not self.db_connection:
            return

        try:
            # Determine academic year if not provided
            if not academic_year:
                academic_year = self._determine_academic_year(
                    result.get('date_completed') or result.get('test_date')
                )

            # Extract common fields
            common_data = self._extract_common_hmh_fields(result, academic_year)

            # Check if this result includes standards breakdown
            standards_data = result.get('standards', []) or result.get('standard_results', [])

            if standards_data:
                # Process standards-level data
                for standard in standards_data:
                    self._save_hmh_assessment_result(common_data, standard)
                    self._save_hmh_standard(standard, common_data.get('Subject'))

            # Save overall summary (if available)
            if result.get('overall_score') or result.get('points_achieved'):
                self._save_hmh_assessment_summary(common_data, result)

            # Save assignment to lookup table
            self._save_hmh_assignment(common_data)

        except Exception as e:
            logger.error(f"Error processing HMH assessment result: {e}")
            logger.error(f"Result data: {json.dumps(result, indent=2)}")

    def _extract_common_hmh_fields(self, result: Dict, academic_year: str) -> Dict:
        """
        Extract common fields used across HMH tables from API result.

        Returns a dictionary with standardized field names matching the HMH schema.
        """
        return {
            'AcademicYear': academic_year,
            'DistrictName': result.get('district_name'),
            'SchoolName': result.get('school_name') or result.get('site_name'),
            'StudentID_SASID': result.get('state_student_id') or result.get('sasid'),
            'StudentID_LASID': result.get('local_student_id') or result.get('lasid') or result.get('student_id'),
            'LastName': result.get('last_name') or result.get('student_last_name'),
            'FirstName': result.get('first_name') or result.get('student_first_name'),
            'StudentGrade': result.get('grade_level') or result.get('student_grade'),
            'ClassName': result.get('class_name') or result.get('section_name'),
            'TeacherLastName': result.get('teacher_last_name'),
            'TeacherFirstName': result.get('teacher_first_name'),
            'ClassGrade': result.get('class_grade_level') or result.get('grade_level'),
            'Subject': result.get('subject') or result.get('subject_name'),
            'ProgramName': result.get('program_name'),
            'Component': result.get('component'),
            'AssignmentName': result.get('assessment_name') or result.get('assessment_title') or result.get('assignment_name'),
            'DateCompleted': self._parse_date(result.get('date_completed') or result.get('test_date')),
            'SchoolID': result.get('school_id') or result.get('site_id'),
        }

    def _save_hmh_assessment_result(self, common_data: Dict, standard: Dict):
        """
        Save a single standards-based assessment result to HMH_Assessment_Results table.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            # Prepare SQL query for SQL Server
            query = """
                INSERT INTO HMH_Assessment_Results (
                    AcademicYear, DistrictName, SchoolName,
                    StudentID_SASID, StudentID_LASID,
                    LastName, FirstName, StudentGrade,
                    ClassName, TeacherLastName, TeacherFirstName, ClassGrade,
                    Subject, ProgramName, Component, AssignmentName,
                    DateCompleted, StandardSet, StandardCodingNumber, StandardDescription,
                    PointsAchieved, PointsPossible, PercentCorrect, SchoolID
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            values = (
                common_data.get('AcademicYear'),
                common_data.get('DistrictName'),
                common_data.get('SchoolName'),
                common_data.get('StudentID_SASID'),
                common_data.get('StudentID_LASID'),
                common_data.get('LastName'),
                common_data.get('FirstName'),
                common_data.get('StudentGrade'),
                common_data.get('ClassName'),
                common_data.get('TeacherLastName'),
                common_data.get('TeacherFirstName'),
                common_data.get('ClassGrade'),
                common_data.get('Subject'),
                common_data.get('ProgramName'),
                common_data.get('Component'),
                common_data.get('AssignmentName'),
                common_data.get('DateCompleted'),
                standard.get('standard_set') or standard.get('set_name'),
                standard.get('standard_code') or standard.get('code'),
                standard.get('standard_description') or standard.get('description'),
                self._safe_decimal(standard.get('points_achieved') or standard.get('score')),
                self._safe_decimal(standard.get('points_possible') or standard.get('max_score')),
                self._calculate_percent(
                    standard.get('points_achieved') or standard.get('score'),
                    standard.get('points_possible') or standard.get('max_score')
                ),
                common_data.get('SchoolID')
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save HMH assessment result: {e}")

    def _save_hmh_assessment_summary(self, common_data: Dict, result: Dict):
        """
        Save overall assessment summary to HMH_Assessment_Summary table.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                INSERT INTO HMH_Assessment_Summary (
                    AcademicYear, SchoolName,
                    StudentID_SASID, StudentID_LASID,
                    LastName, FirstName, StudentGrade,
                    ClassName, TeacherLastName, TeacherFirstName,
                    Subject, ProgramName, Component, AssignmentName,
                    DateCompleted, StandardSet,
                    TotalPointsAchieved, TotalPointsPossible, OverallPercentCorrect,
                    SchoolID
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            total_achieved = self._safe_decimal(
                result.get('points_achieved') or
                result.get('total_score') or
                result.get('raw_score')
            )
            total_possible = self._safe_decimal(
                result.get('points_possible') or
                result.get('max_score')
            )

            values = (
                common_data.get('AcademicYear'),
                common_data.get('SchoolName'),
                common_data.get('StudentID_SASID'),
                common_data.get('StudentID_LASID'),
                common_data.get('LastName'),
                common_data.get('FirstName'),
                common_data.get('StudentGrade'),
                common_data.get('ClassName'),
                common_data.get('TeacherLastName'),
                common_data.get('TeacherFirstName'),
                common_data.get('Subject'),
                common_data.get('ProgramName'),
                common_data.get('Component'),
                common_data.get('AssignmentName'),
                common_data.get('DateCompleted'),
                result.get('standard_set'),
                total_achieved,
                total_possible,
                self._calculate_percent(total_achieved, total_possible),
                common_data.get('SchoolID')
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save HMH assessment summary: {e}")

    def _save_hmh_standard(self, standard: Dict, subject: str = None):
        """
        Save standard to HMH_Standards lookup table.
        Uses MERGE to avoid duplicates.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                MERGE HMH_Standards AS target
                USING (SELECT ? AS StandardSet, ? AS StandardCodingNumber) AS source
                ON (target.StandardSet = source.StandardSet AND target.StandardCodingNumber = source.StandardCodingNumber)
                WHEN NOT MATCHED THEN
                    INSERT (StandardSet, StandardCodingNumber, StandardDescription, Subject)
                    VALUES (?, ?, ?, ?);
            """

            standard_set = standard.get('standard_set') or standard.get('set_name')
            standard_code = standard.get('standard_code') or standard.get('code')
            standard_desc = standard.get('standard_description') or standard.get('description')

            values = (
                standard_set, standard_code,  # For the USING clause
                standard_set, standard_code, standard_desc, subject  # For the INSERT
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save HMH standard: {e}")

    def _save_hmh_assignment(self, common_data: Dict):
        """
        Save assignment to HMH_Assignments lookup table.
        Uses MERGE to avoid duplicates.
        Includes SchoolID to allow same assessment name at different schools.
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                MERGE HMH_Assignments AS target
                USING (SELECT ? AS ProgramName, ? AS Component, ? AS AssignmentName, ? AS SchoolID) AS source
                ON (target.ProgramName = source.ProgramName
                    AND target.Component = source.Component
                    AND target.AssignmentName = source.AssignmentName
                    AND target.SchoolID = source.SchoolID)
                WHEN NOT MATCHED THEN
                    INSERT (ProgramName, Component, AssignmentName, Subject, SchoolID)
                    VALUES (?, ?, ?, ?, ?);
            """

            program = common_data.get('ProgramName')
            component = common_data.get('Component')
            assignment = common_data.get('AssignmentName')
            subject = common_data.get('Subject')
            school_id = common_data.get('SchoolID')

            values = (
                program, component, assignment, school_id,  # For the USING clause
                program, component, assignment, subject, school_id  # For the INSERT
            )

            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()

        except pyodbc.Error as e:
            logger.error(f"Failed to save HMH assignment: {e}")

    # Helper methods

    def _determine_academic_year(self, date_str: str) -> str:
        """
        Determine academic year from a date.
        Academic year runs from July to June (e.g., 2024-07-01 to 2025-06-30 is '2024-2025')
        """
        if not date_str:
            return None

        try:
            date = datetime.strptime(date_str[:10], '%Y-%m-%d')
            if date.month >= 7:
                return f"{date.year}-{date.year + 1}"
            else:
                return f"{date.year - 1}-{date.year}"
        except:
            return None

    def _convert_grade_level_id(self, grade_level_id):
        """
        Convert Illuminate's grade_level_id to actual grade number.
        Illuminate uses: K=1, 1st=2, 2nd=3, 3rd=4, 4th=5, 5th=6, etc.
        We need to subtract 1 to get the actual grade.

        Returns:
            str: Grade level as string ('K' for kindergarten, '0' for pre-K, or number as string)
            None: If grade_level_id is None or invalid
        """
        if grade_level_id is None:
            return None

        try:
            grade_id = int(grade_level_id)
            if grade_id <= 0:
                return None
            elif grade_id == 1:
                return 'K'  # Kindergarten
            else:
                return str(grade_id - 1)  # Subtract 1 for actual grade
        except (ValueError, TypeError):
            logger.warning(f"Invalid grade_level_id: {grade_level_id}")
            return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to SQL Server compatible format (YYYY-MM-DD)"""
        if not date_str:
            return None

        try:
            # Handle various date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                try:
                    dt = datetime.strptime(date_str[:19], fmt)
                    return dt.strftime('%Y-%m-%d')
                except:
                    continue
            return date_str[:10]  # Return first 10 chars as fallback
        except:
            return None

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """Safely convert value to Decimal"""
        if value is None or value == '':
            return None
        try:
            return Decimal(str(value))
        except:
            return None

    def _calculate_percent(self, achieved, possible) -> Optional[str]:
        """Calculate percentage as string"""
        if achieved is None or possible is None or possible == 0:
            return None
        try:
            achieved_dec = Decimal(str(achieved))
            possible_dec = Decimal(str(possible))
            percent = (achieved_dec / possible_dec * 100).quantize(Decimal('0.01'))
            return f"{percent}%"
        except:
            return None


def main():
    """Main execution function"""
    import sys

    # Initialize extractor
    extractor = IlluminateAPIExtractor('config.ini')

    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == 'discover':
        # Run API endpoint discovery
        print("Running API endpoint discovery...")
        print("This will test various endpoints and save response structures to JSON files.")
        extractor.discover_api_endpoints()
        return

    # Configuration for extraction
    school_ids = None  # e.g., [123, 456, 789] - Set to None to extract all schools
    start_date = '2025-09-01'  # Set your date range
    end_date = '2026-06-20'
    academic_year = '2025-2026'  # Set your academic year

    print("=" * 80)
    print("Illuminate Assessment Data Extractor")
    print("=" * 80)
    print("This extracts ALL Illuminate assessment data to Illuminate_* tables.")
    print("=" * 80)
    print(f"School IDs: {school_ids if school_ids else 'All schools'}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Academic Year: {academic_year}")
    print("=" * 80)

    # Run Illuminate extraction (extracts ALL data, not just HMH)
    # HMH data is automatically filtered/synced via sp_Sync_HMH_Data
    total_records = extractor.extract_illuminate_assessment_data(
        school_ids=school_ids,
        start_date=start_date,
        end_date=end_date,
        academic_year=academic_year
    )

    print("=" * 80)
    print(f"Extraction completed successfully!")
    print(f"Total Illuminate assessment records extracted: {total_records}")
    print("=" * 80)
    print()
    print("Data Location:")
    print("  - Illuminate_Assessment_Results - Standards-based assessment data")
    print("  - Illuminate_Assessment_Summary - Overall assessment summaries")
    print("  - Illuminate_Standards - Standards lookup table")
    print("  - Illuminate_Assignments - Assignments lookup table")
    print("=" * 80)


if __name__ == "__main__":
    main()
