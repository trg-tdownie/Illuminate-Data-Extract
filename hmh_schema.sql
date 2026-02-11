-- HMH Assessment Data Schema
-- This schema captures detailed assessment data from HMH Into Literature, Into Math, and Into Reading programs
-- Data includes student performance on standards-based assessments with granular scoring information

-- Main assessment results table
-- Stores individual student assessment attempts with standards-based scoring
CREATE TABLE HMH_Assessment_Results (
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
    Component VARCHAR(200),
    AssignmentName VARCHAR(500),
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
    INDEX IDX_DateCompleted (DateCompleted)
);

-- Summary view for overall assignment scores (aggregated "Overall" records)
CREATE TABLE HMH_Assessment_Summary (
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
    Component VARCHAR(200),
    AssignmentName VARCHAR(500),
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
    INDEX IDX_DateCompleted_Summary (DateCompleted)
);

-- Lookup table for standards
CREATE TABLE HMH_Standards (
    StandardID INT IDENTITY(1,1) PRIMARY KEY,
    StandardSet VARCHAR(500),
    StandardCodingNumber VARCHAR(200),
    StandardDescription VARCHAR(MAX),
    Subject VARCHAR(100),
    CreatedDate DATETIME DEFAULT GETDATE(),

    -- Unique constraint to prevent duplicates
    CONSTRAINT UQ_Standard UNIQUE (StandardSet, StandardCodingNumber)
);

-- Lookup table for assignments
CREATE TABLE HMH_Assignments (
    AssignmentID INT IDENTITY(1,1) PRIMARY KEY,
    ProgramName VARCHAR(200),
    Component VARCHAR(200),
    AssignmentName VARCHAR(500),
    Subject VARCHAR(100),
    CreatedDate DATETIME DEFAULT GETDATE(),

    -- Unique constraint to prevent duplicates
    CONSTRAINT UQ_Assignment UNIQUE (ProgramName, Component, AssignmentName)
);
