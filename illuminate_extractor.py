"""
Illuminate API Assessment Data Extractor for HMH Assessments
Extracts HMH assessment data from Illuminate/Renaissance DnA API
with standards-based scoring and stores in SQL Server database
"""

import requests
import json
import pyodbc
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
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, auth=self.oauth, params=params, timeout=30)
            logger.info(f"Request URL: {url}")
            logger.info(f"Response Status: {response.status_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")
            logger.info(f"Response Text (first 500 chars): {response.text[:500]}")
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
            # Try primary endpoint for standards-based assessment data
            logger.info("Attempting to extract from students/assessment_standards endpoint...")
            count = self._extract_illuminate_from_standards_endpoint(
                school_ids, start_date, end_date, academic_year
            )
            total_extracted += count

            if count == 0:
                logger.info("No data from standards endpoint, trying students/assessments...")
                count = self._extract_illuminate_from_assessments_endpoint(
                    school_ids, start_date, end_date, academic_year
                )
                total_extracted += count

            logger.info("=" * 60)
            logger.info(f"Illuminate extraction completed. Total records: {total_extracted}")
            logger.info("=" * 60)

            # Optionally sync HMH data automatically
            if total_extracted > 0:
                logger.info("Syncing HMH data from Illuminate tables...")
                self._sync_hmh_data()

            return total_extracted

        except Exception as e:
            logger.error(f"Error during Illuminate extraction: {e}")
            return total_extracted
        finally:
            self.disconnect_db()

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
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                MERGE Illuminate_Assignments AS target
                USING (SELECT ? AS ProgramName, ? AS Component, ? AS AssignmentName) AS source
                ON (target.ProgramName = source.ProgramName
                    AND target.Component = source.Component
                    AND target.AssignmentName = source.AssignmentName)
                WHEN NOT MATCHED THEN
                    INSERT (ProgramName, Publisher, Component, AssignmentName, IlluminateAssessmentID, Subject)
                    VALUES (?, ?, ?, ?, ?, ?);
            """

            program = common_data.get('ProgramName')
            publisher = common_data.get('Publisher')
            component = common_data.get('Component')
            assignment = common_data.get('AssignmentName')
            assessment_id = common_data.get('AssessmentID')
            subject = common_data.get('Subject')

            values = (
                program, component, assignment,  # For the USING clause
                program, publisher, component, assignment, assessment_id, subject  # For the INSERT
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
        """
        if not self.db_connection:
            return

        try:
            cursor = self.db_connection.cursor()

            query = """
                MERGE HMH_Assignments AS target
                USING (SELECT ? AS ProgramName, ? AS Component, ? AS AssignmentName) AS source
                ON (target.ProgramName = source.ProgramName
                    AND target.Component = source.Component
                    AND target.AssignmentName = source.AssignmentName)
                WHEN NOT MATCHED THEN
                    INSERT (ProgramName, Component, AssignmentName, Subject)
                    VALUES (?, ?, ?, ?);
            """

            program = common_data.get('ProgramName')
            component = common_data.get('Component')
            assignment = common_data.get('AssignmentName')
            subject = common_data.get('Subject')

            values = (
                program, component, assignment,  # For the USING clause
                program, component, assignment, subject  # For the INSERT
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
    start_date = '2024-01-01'  # Set your date range
    end_date = '2024-12-31'
    academic_year = '2024-2025'  # Set your academic year

    print("=" * 80)
    print("Illuminate Assessment Data Extractor")
    print("=" * 80)
    print("This extracts ALL Illuminate assessment data to Illuminate_* tables,")
    print("then automatically syncs HMH data to HMH_* tables.")
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
    print(f"HMH data has been automatically synced to HMH_* tables.")
    print("=" * 80)
    print()
    print("Data Location:")
    print("  - All Illuminate data: Illuminate_Assessment_Results, Illuminate_Assessment_Summary")
    print("  - HMH data only: HMH_Assessment_Results, HMH_Assessment_Summary")
    print("  - To manually re-sync HMH data: EXEC sp_Sync_HMH_Data")
    print("=" * 80)


if __name__ == "__main__":
    main()
