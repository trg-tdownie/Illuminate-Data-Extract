-- Illuminate API Assessment Data Schema
-- Database schema for storing assessment data from Illuminate/Renaissance DnA API

-- Schools/Sites table
CREATE TABLE IF NOT EXISTS schools (
    school_id INT PRIMARY KEY,
    school_name VARCHAR(255),
    district_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Assessments table
CREATE TABLE IF NOT EXISTS assessments (
    assessment_id INT PRIMARY KEY,
    local_assessment_id VARCHAR(100),
    title VARCHAR(500),
    description TEXT,
    subject_id INT,
    subject_name VARCHAR(255),
    scope_id INT,
    scope_name VARCHAR(255),
    author_id INT,
    author_name VARCHAR(255),
    version INT,
    created_date DATE,
    modified_date DATE,
    deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_local_assessment_id (local_assessment_id),
    INDEX idx_subject_id (subject_id),
    INDEX idx_created_date (created_date)
);

-- Performance bands for assessments
CREATE TABLE IF NOT EXISTS performance_bands (
    band_id INT AUTO_INCREMENT PRIMARY KEY,
    assessment_id INT,
    band_name VARCHAR(100),
    min_score DECIMAL(10,2),
    max_score DECIMAL(10,2),
    color VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    INDEX idx_assessment_id (assessment_id)
);

-- Assessment questions
CREATE TABLE IF NOT EXISTS assessment_questions (
    question_id INT AUTO_INCREMENT PRIMARY KEY,
    assessment_id INT,
    question_number INT,
    question_text TEXT,
    question_type VARCHAR(50),
    max_points DECIMAL(10,2),
    correct_answer TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    INDEX idx_assessment_id (assessment_id)
);

-- Answer choices for questions
CREATE TABLE IF NOT EXISTS answer_choices (
    choice_id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT,
    choice_letter VARCHAR(10),
    choice_text TEXT,
    is_correct BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES assessment_questions(question_id) ON DELETE CASCADE,
    INDEX idx_question_id (question_id)
);

-- Standards alignment
CREATE TABLE IF NOT EXISTS standards (
    standard_id INT PRIMARY KEY,
    standard_code VARCHAR(100),
    standard_description TEXT,
    subject VARCHAR(100),
    grade_level VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_standard_code (standard_code)
);

-- Question to standards mapping
CREATE TABLE IF NOT EXISTS question_standards (
    mapping_id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT,
    standard_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES assessment_questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (standard_id) REFERENCES standards(standard_id) ON DELETE CASCADE,
    UNIQUE KEY unique_question_standard (question_id, standard_id),
    INDEX idx_question_id (question_id),
    INDEX idx_standard_id (standard_id)
);

-- Students table
CREATE TABLE IF NOT EXISTS students (
    student_id INT PRIMARY KEY,
    local_student_id VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    grade_level VARCHAR(20),
    school_id INT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(school_id),
    INDEX idx_local_student_id (local_student_id),
    INDEX idx_school_id (school_id)
);

-- Student assessment scores
CREATE TABLE IF NOT EXISTS student_scores (
    score_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    assessment_id INT,
    local_student_id VARCHAR(100),
    test_date DATE,
    raw_score DECIMAL(10,2),
    percent_correct DECIMAL(5,2),
    performance_band VARCHAR(100),
    version INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    INDEX idx_student_id (student_id),
    INDEX idx_assessment_id (assessment_id),
    INDEX idx_test_date (test_date),
    INDEX idx_student_assessment (student_id, assessment_id, test_date)
);

-- Student responses to individual questions
CREATE TABLE IF NOT EXISTS student_responses (
    response_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    score_id BIGINT,
    student_id INT,
    assessment_id INT,
    question_id INT,
    response TEXT,
    points_earned DECIMAL(10,2),
    is_correct BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (score_id) REFERENCES student_scores(score_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES assessment_questions(question_id),
    INDEX idx_score_id (score_id),
    INDEX idx_student_id (student_id),
    INDEX idx_assessment_id (assessment_id)
);

-- API extraction log
CREATE TABLE IF NOT EXISTS api_extraction_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    endpoint VARCHAR(255),
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    records_extracted INT,
    status VARCHAR(50),
    error_message TEXT,
    INDEX idx_extraction_date (extraction_date),
    INDEX idx_endpoint (endpoint)
);
