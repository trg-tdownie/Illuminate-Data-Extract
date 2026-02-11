-- Illuminate Assessment Data Schema
-- This schema captures ALL assessment data from Illuminate/Renaissance DnA API
-- This is the main landing zone for all Illuminate data before filtering to specific programs

-- Main assessment results table - ALL Illuminate assessments
-- Stores individual student assessment attempts with standards-based scoring
CREATE TABLE Illuminate_Assessment_Results (
    ResultID INT IDENTITY(1,1) PRIMARY KEY,
    AcademicYear VARCHAR(20) NOT NULL,
    DistrictName VARCHAR(200),
    SchoolName VARCHAR(200) NOT NULL,
    StudentID_SASID VARCHAR(50),
    StudentID_LASID VARCHAR(50),
    LastName VARCHAR(100),
    FirstName VARCHAR(100),
    StudentGrade VARCHAR(10),
    ClassName VARCHAR(200),
    TeacherLastName VARCHAR(100),
    TeacherFirstName VARCHAR(100),
    ClassGrade VARCHAR(10),
    Subject VARCHAR(100),
    ProgramName VARCHAR(200),
    Publisher VARCHAR(200),
    Component VARCHAR(200),
    AssignmentName VARCHAR(500),
    AssessmentID INT,
    DateCompleted DATE,
    StandardSet VARCHAR(500),
    StandardCodingNumber VARCHAR(200),
    StandardDescription VARCHAR(MAX),
    PointsAchieved DECIMAL(10,2),
    PointsPossible DECIMAL(10,2),
    PercentCorrect VARCHAR(20),
    SchoolID INT,
    CreatedDate DATETIME DEFAULT GETDATE(),
    UpdatedDate DATETIME DEFAULT GETDATE(),

    -- Indexes for common queries
    INDEX IDX_Student (StudentID_SASID, StudentID_LASID),
    INDEX IDX_Assignment (AssignmentName, DateCompleted),
    INDEX IDX_School (SchoolID, SchoolName),
    INDEX IDX_Teacher (TeacherLastName, TeacherFirstName),
    INDEX IDX_Standard (StandardCodingNumber),
    INDEX IDX_DateCompleted (DateCompleted),
    INDEX IDX_Program (ProgramName),
    INDEX IDX_AssessmentID (AssessmentID)
);

-- Summary view for overall assignment scores (aggregated "Overall" records)
CREATE TABLE Illuminate_Assessment_Summary (
    SummaryID INT IDENTITY(1,1) PRIMARY KEY,
    AcademicYear VARCHAR(20) NOT NULL,
    SchoolName VARCHAR(200) NOT NULL,
    StudentID_SASID VARCHAR(50),
    StudentID_LASID VARCHAR(50),
    LastName VARCHAR(100),
    FirstName VARCHAR(100),
    StudentGrade VARCHAR(10),
    ClassName VARCHAR(200),
    TeacherLastName VARCHAR(100),
    TeacherFirstName VARCHAR(100),
    Subject VARCHAR(100),
    ProgramName VARCHAR(200),
    Publisher VARCHAR(200),
    Component VARCHAR(200),
    AssignmentName VARCHAR(500),
    AssessmentID INT,
    DateCompleted DATE,
    StandardSet VARCHAR(500),
    TotalPointsAchieved DECIMAL(10,2),
    TotalPointsPossible DECIMAL(10,2),
    OverallPercentCorrect VARCHAR(20),
    SchoolID INT,
    CreatedDate DATETIME DEFAULT GETDATE(),
    UpdatedDate DATETIME DEFAULT GETDATE(),

    -- Indexes for common queries
    INDEX IDX_Student_Summary (StudentID_SASID, StudentID_LASID),
    INDEX IDX_Assignment_Summary (AssignmentName, DateCompleted),
    INDEX IDX_School_Summary (SchoolID, SchoolName),
    INDEX IDX_DateCompleted_Summary (DateCompleted),
    INDEX IDX_Program_Summary (ProgramName),
    INDEX IDX_AssessmentID_Summary (AssessmentID)
);

-- Lookup table for standards
CREATE TABLE Illuminate_Standards (
    StandardID INT IDENTITY(1,1) PRIMARY KEY,
    StandardSet VARCHAR(500),
    StandardCodingNumber VARCHAR(200),
    StandardDescription VARCHAR(MAX),
    Subject VARCHAR(100),
    CreatedDate DATETIME DEFAULT GETDATE(),

    -- Unique constraint to prevent duplicates
    CONSTRAINT UQ_Illuminate_Standard UNIQUE (StandardSet, StandardCodingNumber)
);

-- Lookup table for assignments
CREATE TABLE Illuminate_Assignments (
    AssignmentID INT IDENTITY(1,1) PRIMARY KEY,
    ProgramName VARCHAR(200),
    Publisher VARCHAR(200),
    Component VARCHAR(200),
    AssignmentName VARCHAR(500),
    IlluminateAssessmentID INT,
    Subject VARCHAR(100),
    CreatedDate DATETIME DEFAULT GETDATE(),

    -- Unique constraint to prevent duplicates
    CONSTRAINT UQ_Illuminate_Assignment UNIQUE (ProgramName, Component, AssignmentName)
);

-- View to identify HMH assessments from Illuminate data
CREATE VIEW vw_HMH_Assessments AS
SELECT *
FROM Illuminate_Assessment_Results
WHERE
    LOWER(ProgramName) LIKE '%hmh%'
    OR LOWER(ProgramName) LIKE '%into literature%'
    OR LOWER(ProgramName) LIKE '%into math%'
    OR LOWER(ProgramName) LIKE '%into reading%'
    OR LOWER(Publisher) LIKE '%houghton mifflin%'
    OR LOWER(Publisher) LIKE '%harcourt%'
    OR LOWER(AssignmentName) LIKE '%hmh%'
    OR LOWER(AssignmentName) LIKE '%into literature%'
    OR LOWER(AssignmentName) LIKE '%into math%'
    OR LOWER(AssignmentName) LIKE '%into reading%';
GO

-- Stored procedure to sync HMH data from Illuminate tables to HMH tables
CREATE PROCEDURE sp_Sync_HMH_Data
AS
BEGIN
    SET NOCOUNT ON;

    -- Sync HMH_Assessment_Results from Illuminate data
    INSERT INTO HMH_Assessment_Results (
        AcademicYear, DistrictName, SchoolName,
        StudentID_SASID, StudentID_LASID,
        LastName, FirstName, StudentGrade,
        ClassName, TeacherLastName, TeacherFirstName, ClassGrade,
        Subject, ProgramName, Component, AssignmentName,
        DateCompleted, StandardSet, StandardCodingNumber, StandardDescription,
        PointsAchieved, PointsPossible, PercentCorrect, SchoolID
    )
    SELECT
        AcademicYear, DistrictName, SchoolName,
        StudentID_SASID, StudentID_LASID,
        LastName, FirstName, StudentGrade,
        ClassName, TeacherLastName, TeacherFirstName, ClassGrade,
        Subject, ProgramName, Component, AssignmentName,
        DateCompleted, StandardSet, StandardCodingNumber, StandardDescription,
        PointsAchieved, PointsPossible, PercentCorrect, SchoolID
    FROM vw_HMH_Assessments
    WHERE NOT EXISTS (
        SELECT 1 FROM HMH_Assessment_Results hmh
        WHERE hmh.StudentID_LASID = vw_HMH_Assessments.StudentID_LASID
        AND hmh.AssignmentName = vw_HMH_Assessments.AssignmentName
        AND hmh.DateCompleted = vw_HMH_Assessments.DateCompleted
        AND hmh.StandardCodingNumber = vw_HMH_Assessments.StandardCodingNumber
    );

    -- Sync HMH_Assessment_Summary
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
    SELECT
        AcademicYear, SchoolName,
        StudentID_SASID, StudentID_LASID,
        LastName, FirstName, StudentGrade,
        ClassName, TeacherLastName, TeacherFirstName,
        Subject, ProgramName, Component, AssignmentName,
        DateCompleted, StandardSet,
        TotalPointsAchieved, TotalPointsPossible, OverallPercentCorrect,
        SchoolID
    FROM Illuminate_Assessment_Summary
    WHERE (
        LOWER(ProgramName) LIKE '%hmh%'
        OR LOWER(ProgramName) LIKE '%into literature%'
        OR LOWER(ProgramName) LIKE '%into math%'
        OR LOWER(ProgramName) LIKE '%into reading%'
    )
    AND NOT EXISTS (
        SELECT 1 FROM HMH_Assessment_Summary hmh
        WHERE hmh.StudentID_LASID = Illuminate_Assessment_Summary.StudentID_LASID
        AND hmh.AssignmentName = Illuminate_Assessment_Summary.AssignmentName
        AND hmh.DateCompleted = Illuminate_Assessment_Summary.DateCompleted
    );

    -- Sync HMH_Standards
    INSERT INTO HMH_Standards (StandardSet, StandardCodingNumber, StandardDescription, Subject)
    SELECT DISTINCT StandardSet, StandardCodingNumber, StandardDescription, Subject
    FROM Illuminate_Standards
    WHERE EXISTS (
        SELECT 1 FROM vw_HMH_Assessments hmh
        WHERE hmh.StandardSet = Illuminate_Standards.StandardSet
        AND hmh.StandardCodingNumber = Illuminate_Standards.StandardCodingNumber
    )
    AND NOT EXISTS (
        SELECT 1 FROM HMH_Standards hmh
        WHERE hmh.StandardSet = Illuminate_Standards.StandardSet
        AND hmh.StandardCodingNumber = Illuminate_Standards.StandardCodingNumber
    );

    -- Sync HMH_Assignments
    INSERT INTO HMH_Assignments (ProgramName, Component, AssignmentName, Subject)
    SELECT DISTINCT ProgramName, Component, AssignmentName, Subject
    FROM Illuminate_Assignments
    WHERE (
        LOWER(ProgramName) LIKE '%hmh%'
        OR LOWER(ProgramName) LIKE '%into literature%'
        OR LOWER(ProgramName) LIKE '%into math%'
        OR LOWER(ProgramName) LIKE '%into reading%'
    )
    AND NOT EXISTS (
        SELECT 1 FROM HMH_Assignments hmh
        WHERE hmh.ProgramName = Illuminate_Assignments.ProgramName
        AND hmh.Component = Illuminate_Assignments.Component
        AND hmh.AssignmentName = Illuminate_Assignments.AssignmentName
    );

    SELECT
        'Sync completed' AS Status,
        (SELECT COUNT(*) FROM HMH_Assessment_Results) AS HMH_Results_Count,
        (SELECT COUNT(*) FROM HMH_Assessment_Summary) AS HMH_Summary_Count,
        (SELECT COUNT(*) FROM HMH_Standards) AS HMH_Standards_Count,
        (SELECT COUNT(*) FROM HMH_Assignments) AS HMH_Assignments_Count;
END;
GO
